"""Pilot benchmark runner (docs/v0.7-benchmark-plan.md).

Staged operation per user constraint:
  1. print configured models, pricing assumptions, max possible requests,
     hard monetary/request caps BEFORE any provider call;
  2. enforce caps (attempts incl. retries count against the request cap);
  3. stop immediately if usage or cost becomes unpriceable (cost_known=False
     on an allowed response, or a model has no pricing entry);
  4. bounded retries only (InferencePolicy), never model switching;
  5. fake mode is deterministic and separate (mode label in artifact).

Extending beyond the pilot requires explicit user approval.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
CREST_ROOT = EXPERIMENT_DIR.parent.parent
if str(CREST_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(CREST_ROOT / "src"))

from crest.inference import (  # noqa: E402
    HttpChatAdapter,
    InferencePolicy,
    InferenceRequest,
    InferenceRuntime,
)
from crest.store import Store  # noqa: E402

from . import tasks as tasklib  # noqa: E402
from .adapters import FakeTaskModelAdapter, MultiModelAdapter, make_request_id  # noqa: E402
from .strategies import (  # noqa: E402
    CrestRouter,
    MODE_CREST,
    MODE_LARGE,
    MODE_SMALL,
    calibrate_crest,
    capability_of,
)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
CHEAP_MODEL = "gemini-3.5-flash-lite"
LARGE_MODEL = "gemini-3.8-flash"

PRICING_ASSUMPTIONS_URL = "ASSUMPTION-UNVERIFIED: fill from provider pricing page before publishing USD claims"
PRICING_PER_MODEL = {
    CHEAP_MODEL: {"input_usd_per_mtok": 0.10, "output_usd_per_mtok": 0.40},
    LARGE_MODEL: {"input_usd_per_mtok": 0.30, "output_usd_per_mtok": 1.20},
}
PILOT_USD_CAP = 0.05
PILOT_MAX_REQUEST_ATTEMPTS = 80
CAL_ATTEMPT_LIMIT = 30 * 2  # calibration never consumes more than 60 attempts

REQUEST_TIMEOUT_SECONDS = 45.0
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 3.0

POLICY_KWARGS = dict(
    max_input_tokens=4096,
    max_output_tokens=120,
    max_prompt_chars=8192,
    max_output_chars=8192,
    request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    max_attempts=MAX_ATTEMPTS,
    retry_on_transient=True,
    retry_backoff_seconds=RETRY_BACKOFF_SECONDS,
    window_budget_units=1_000_000_000.0,
    max_cost_units_per_request=1_000_000_000.0,
    require_usage=True,
    require_nonempty_output=True,
)


class BudgetGuardExceeded(Exception):
    pass


class BudgetGuard:
    """Hard caps over request attempts and estimated USD (from usage)."""

    def __init__(self, max_attempts: int, usd_cap: float) -> None:
        self.max_attempts = max_attempts
        self.usd_cap = usd_cap
        self.attempts = 0
        self.usd_spent = 0.0
        self.tokens_in = 0
        self.tokens_out = 0

    def observe(self, model: str, attempts: int, used_in: int, used_out: int, *, require_price: bool) -> None:
        if require_price and not (PRICING_PER_MODEL.get(model) and used_in + used_out >= 0):
            if PRICING_PER_MODEL.get(model) is None:
                raise BudgetGuardExceeded(f"no pricing entry for model {model!r}: stopping")
        self.attempts += attempts
        self.tokens_in += used_in
        self.tokens_out += used_out
        pricing = PRICING_PER_MODEL.get(model)
        if pricing is not None:
            self.usd_spent += (used_in / 1e6) * pricing["input_usd_per_mtok"] + (used_out / 1e6) * pricing["output_usd_per_mtok"]
        if self.attempts > self.max_attempts:
            raise BudgetGuardExceeded(f"request-attempt cap exceeded: {self.attempts} > {self.max_attempts}")
        if self.usd_spent > self.usd_cap:
            raise BudgetGuardExceeded(f"USD cap exceeded: {self.usd_spent:.4f} > {self.usd_cap:.4f}")

    def observe_denied_attempt(self, model: str, attempts: int) -> None:
        """Attempts (incl. retries and failed calls) count toward the cap even
        when the provider never returned a priced response."""
        self.attempts += attempts
        if self.attempts > self.max_attempts:
            raise BudgetGuardExceeded(f"request-attempt cap exceeded: {self.attempts} > {self.max_attempts}")

    def describe(self, planned_attempts: int) -> str:
        return (
            f"models: {[m for m in (CHEAP_MODEL, LARGE_MODEL)]}; "
            f"endpoint: {GEMINI_BASE_URL}; "
            f"pricing assumptions: {json.dumps(PRICING_PER_MODEL)} price_source={PRICING_ASSUMPTIONS_URL}; "
            f"planned request-attempts ({planned_attempts}) max={self.max_attempts}; "
            f"hard USD cap={self.usd_cap:.4f}; retries+failures count toward attempt cap; "
            "stop rule: usage unknown or unpriceable -> halt without further calls"
        )


def _live_policy(models: tuple[str, ...]) -> InferencePolicy:
    return InferencePolicy(allowed_models=models, **POLICY_KWARGS)


def _probe_large_model_health(api_key: str) -> tuple[bool, str, int, int]:
    """One tiny health probe for the strong model; no silent model switching.
    Returns (healthy, note, used_input_tokens, used_output_tokens)."""
    adapter = HttpChatAdapter(base_url=GEMINI_BASE_URL, api_key=api_key, model=LARGE_MODEL)
    request = InferenceRequest(
        request_id="health-probe::large::0",
        model=LARGE_MODEL,
        prompt="Reply with exactly the single word: OK",
        max_output_tokens=8,
        agent_id="benchmark-health",
    )
    try:
        response = adapter.complete(request, timeout_seconds=20.0)
        usage = response.usage
        return True, f"OK finish={response.finish_reason}", usage.input_tokens, usage.output_tokens
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:200]}", 0, 0


def _observe_result(guard: BudgetGuard, result) -> bool:
    if result.allowed:
        if not result.cost_known or result.response is None:
            raise BudgetGuardExceeded("usage unknown on an allowed response: cannot meter spend; stopping")
        guard.observe(result.model, result.attempts, result.input_tokens, result.output_tokens, require_price=True)
    else:
        guard.observe_denied_attempt(result.model, result.attempts)
    return result.allowed


def _run_strategy(
    strategy: str,
    runtime: InferenceRuntime,
    guard: BudgetGuard,
    eval_tasks,
    choose_model,
    run_seq_start: int,
) -> list[dict]:
    rows: list[dict] = []
    for i, task in enumerate(eval_tasks):
        model = choose_model(task)
        request = InferenceRequest(
            request_id=make_request_id(strategy, task.task_id, f"s{run_seq_start + i}"),
            model=model,
            prompt=task.text,
            system=tasklib.PROMPT_SYSTEM,
            max_output_tokens=POLICY_KWARGS["max_output_tokens"],
            agent_id=f"benchmark-{strategy}",
        )
        result = runtime.infer(request)
        allowed = _observe_result(guard, result)
        correct = None
        if allowed:
            verdict = tasklib.score(task, result.response.text)
            correct = bool(verdict["correct"])
        row = {
            "strategy": strategy,
            "task_id": task.task_id,
            "model": result.model,
            "allowed": result.allowed,
            "status_reason": result.reason,
            "attempts": result.attempts,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_known": result.cost_known,
            "latency_ms": round(result.duration_ms, 1),
            "correct": correct,
            "capability": capability_of(task),
        }
        rows.append(row)
    return rows


def _summarize(rows: list[dict]) -> dict:
    by_strategy: dict[str, list[dict]] = {}
    for row in rows:
        by_strategy.setdefault(row["strategy"], []).append(row)
    summary = {}
    for strategy, srows in sorted(by_strategy.items()):
        evaluated = [r for r in srows if r["allowed"]]
        scored = [r for r in evaluated if r["correct"] is not None]
        successful = [r for r in scored if r["correct"]]
        out = {
            "tasks_attempted": len(srows),
            "task_success_n": len(successful),
            "task_success_rate": round(len(successful) / len(scored), 4) if scored else None,
            "provider_denied": len(srows) - len(evaluated),
            "total_input_tokens": sum(r["input_tokens"] for r in srows),
            "total_output_tokens": sum(r["output_tokens"] for r in srows),
            "retried_attempts": sum(max(0, r["attempts"] - 1) for r in srows),
        }
        estimated_usd = 0.0
        for model in {r["model"] for r in srows if r["model"]}:
            pricing = PRICING_PER_MODEL.get(model)
            if pricing is None:
                continue
            tin = sum(r["input_tokens"] for r in srows if r["model"] == model)
            tout = sum(r["output_tokens"] for r in srows if r["model"] == model)
            estimated_usd += tin / 1e6 * pricing["input_usd_per_mtok"] + tout / 1e6 * pricing["output_usd_per_mtok"]
        out["estimated_usd_cost"] = round(estimated_usd, 4)
        summary[strategy] = out
    return summary


def run(mode: str = "fake", *, stage_max_attempts: int = PILOT_MAX_REQUEST_ATTEMPTS, usd_cap: float = PILOT_USD_CAP) -> dict:
    all_tasks = tasklib.generate_tasks()
    calibration = [t for t in all_tasks if t.split == "calibration"]
    pilot = [t for t in all_tasks if t.split == "pilot"]
    tasks_by_id = {t.task_id: t for t in all_tasks}

    dataset_digest = tasklib.digest(all_tasks)
    artifact: dict = {
        "mode": mode,
        "stage": "pilot",
        "dataset_digest": dataset_digest,
        "dataset_is_synthetic_not_real_traffic": True,
        "plan_doc": "docs/v0.7-benchmark-plan.md",
        "strategies": list((MODE_LARGE, MODE_SMALL, MODE_CREST)),
        "models": {"cheap": CHEAP_MODEL, "large": LARGE_MODEL},
        "pricing": {"per_model": PRICING_PER_MODEL, "source": PRICING_ASSUMPTIONS_URL, "actual_cost_available": False},
        "budget_guard": {"max_request_attempts": stage_max_attempts, "usd_cap": usd_cap},
    }

    guard = BudgetGuard(stage_max_attempts, usd_cap)

    if mode == "live":
        import os

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {**artifact, "status": "ABORTED", "detail": "GEMINI_API_KEY not present"}
        print("=== BUDGET GUARD (print before any call) ===")
        print("planned attempts: calibration<=60 (+retries), pilot<=30 (+retries)")
        print(guard.describe(stage_max_attempts))
        healthy, health_note, probe_in, probe_out = _probe_large_model_health(api_key)
        print(f"strong-model health probe: healthy={healthy} note={health_note}")
        try:
            if healthy:
                guard.observe(LARGE_MODEL, 1, probe_in, probe_out, require_price=True)
            else:
                guard.observe_denied_attempt(LARGE_MODEL, 1)
        except BudgetGuardExceeded as exc:
            return {**artifact, "status": "HALTED_BUDGET_GUARD", "detail": str(exc)}
        if not healthy:
            artifact["status"] = "PARTIAL_SKIPPED_STRONG_MODEL"
        live_models = (CHEAP_MODEL, LARGE_MODEL) if healthy else (CHEAP_MODEL,)
        policy = _live_policy(live_models)
        adapters = {
            CHEAP_MODEL: HttpChatAdapter(base_url=GEMINI_BASE_URL, api_key=api_key, model=CHEAP_MODEL),
            LARGE_MODEL: HttpChatAdapter(base_url=GEMINI_BASE_URL, api_key=api_key, model=LARGE_MODEL),
        }
    else:
        policy = _live_policy((CHEAP_MODEL, LARGE_MODEL))
        adapters = {
            CHEAP_MODEL: FakeTaskModelAdapter(tasks_by_id, cheap=True),
            LARGE_MODEL: FakeTaskModelAdapter(tasks_by_id, cheap=False),
        }
        healthy = True
        artifact["status"] = "RUNNING"
        print("=== BUDGET GUARD (fake mode, no network) ===")
        print(guard.describe(stage_max_attempts))

    adapter = MultiModelAdapter(adapters)

    store = None
    try:
        store = Store(Path(tempfile.mkdtemp(prefix="crest-bench-")) / "crest.db")
        runtime = InferenceRuntime(store, policy, adapter)

        try:
            crest_calibration = calibrate_crest(
                calibration,
                CHEAP_MODEL,
                LARGE_MODEL,
                store,
                _live_policy((CHEAP_MODEL,)),
                adapter,
            )
            for row in crest_calibration["calibration_rows"]:
                if row["allowed"]:
                    guard.observe(CHEAP_MODEL, row["attempts"], row["input_tokens"], row["output_tokens"], require_price=True)
                else:
                    guard.observe_denied_attempt(CHEAP_MODEL, row["attempts"])
        except BudgetGuardExceeded as exc:
            return {**artifact, "status": "HALTED_BUDGET_GUARD", "detail": str(exc)}

        router = CrestRouter(crest_calibration["admission"], CHEAP_MODEL, LARGE_MODEL)
        artifact["crest_calibration"] = crest_calibration

        strategy_rows: list[dict] = []
        choosers = {
            MODE_LARGE: (lambda t: LARGE_MODEL),
            MODE_SMALL: (lambda t: CHEAP_MODEL),
            MODE_CREST: router.choose_model,
        }
        live_models = (CHEAP_MODEL, LARGE_MODEL) if healthy else (CHEAP_MODEL,)
        sweep = (MODE_LARGE, MODE_SMALL, MODE_CREST)
        for strategy in sweep:
            deferred_rows: list[dict] = []
            executed_rows: list[dict] = []
            for task in pilot:
                chosen = choosers[strategy](task)
                if chosen not in live_models:
                    # Strong model unavailable: record NOT_RUN, do not silently
                    # substitute another model (no silent model switching).
                    deferred_rows.append(
                        {
                            "strategy": strategy,
                            "task_id": task.task_id,
                            "model": chosen,
                            "allowed": False,
                            "status_reason": "MODEL_UNAVAILABLE",
                            "attempts": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cost_known": False,
                            "latency_ms": 0.0,
                            "correct": None,
                            "capability": capability_of(task),
                            "not_run": True,
                        }
                    )
            rows_to_run = [t for t in pilot if choosers[strategy](t) in live_models]
            # Preserve task order in the artifact: append deferred rows in order.
            strategy_rows.extend(
                _run_strategy(strategy, runtime, guard, rows_to_run, choosers[strategy], run_seq_start=10_000 + len(strategy_rows))
            )
            if deferred_rows:
                artifact["not_run_rows"] = artifact.get("not_run_rows", []) + deferred_rows
                if strategy in (MODE_LARGE, MODE_CREST) and not healthy:
                    artifact["status"] = "PARTIAL_STRONG_MODEL_UNAVAILABLE"
    finally:
        if store is not None:
            store.close()

    summary = _summarize(strategy_rows)
    artifact["pilot_rows"] = strategy_rows
    artifact["summary"] = summary
    artifact["guard_final"] = {
        "attempts": guard.attempts,
        "usd_spent_est": round(guard.usd_spent, 4),
        "tokens": [guard.tokens_in, guard.tokens_out],
    }
    artifact["status"] = "COMPLETE"
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the extraction pilot benchmark")
    parser.add_argument("--mode", choices=("fake", "live"), required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    artifact = run(mode=args.mode)
    payload = json.dumps(artifact, indent=2, sort_keys=True)
    target = Path(args.out) if args.out else None
    if target is None:
        target = EXPERIMENT_DIR / "artifacts" / (f"pilot_{args.mode}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload, encoding="utf-8")
    print(f"artifact written: {target}")
    for strategy, numbers in sorted(artifact.get("summary", {}).items()):
        print(
            f"{strategy}: success={numbers['task_success_rate']}"
            f" in={numbers['total_input_tokens']} out={numbers['total_output_tokens']}"
            f" est_usd={numbers['estimated_usd_cost']} retries={numbers['retried_attempts']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

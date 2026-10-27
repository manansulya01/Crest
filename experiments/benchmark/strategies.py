"""Execution strategies compared by the benchmark (identical inputs elsewhere).

- fixed_large / cost_aware_small: single-model baselines.
- crest_policy: evidence-gated admission. The cheap model is admitted per
  text-derived capability class only when calibration against labeled
  calibration tasks yields a binomial failure upper bound below threshold
  (same Wilson-style bound as ``crest.policy.failure_upper_bound_at``).
  Gold labels legislate the admission table during calibration only;
  held-out gold labels are never consulted by routing.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from crest.policy import failure_upper_bound_at

from crest.inference import InferencePolicy, InferenceRequest, InferenceRuntime
from crest.store import Store
from .tasks import Task, derive_features
from . import tasks as tasklib

MODE_LARGE = "fixed_large"
MODE_SMALL = "cost_aware_small"
MODE_CREST = "crest_policy"

ALL_STRATEGIES = (MODE_LARGE, MODE_SMALL, MODE_CREST)


def fixed_large(task: Task) -> str:  # pragma: no cover - trivial
    return "LARGE"


def cost_aware_small(task: Task) -> str:  # pragma: no cover - trivial
    return "SMALL"


def capability_of(task: Task, features_fn=None) -> str:
    if features_fn is None:
        from . import tasks as _t
        features_fn = _t.derive_features
    features = features_fn(task.text)
    if isinstance(features, dict):
        multi = bool(features.get("multi_constraint") or features.get("multi_topic", False))
    else:
        multi = bool(getattr(features, "multi_constraint", getattr(features, "multi_topic", False)))
    return "multi_topic" if multi else "single_topic"


def calibrate_crest(
    calibration_tasks: Iterable[Task],
    cheap_model_name: str,
    large_model_name: str,
    store: Store,
    policy: InferencePolicy,
    adapter: MultiModelAdapter,
    *,
    score_fn=None,
    system_prompt: str = "",
    success_threshold: float = 0.05,
) -> dict:
    if score_fn is None:
        from . import tasks as _t
        score_fn = _t.score
    """Run the cheap model over calibration tasks, score them, and derive the
    admission table per capability class using the same failure bound used by
    CREST admission policy. Returns {"admission": {class: bool}, ...}."""
    runtime = InferenceRuntime(store, policy, adapter)
    results: dict[str, list[bool]] = {"single_topic": [], "multi_topic": []}
    calibration_rows = []
    for i, task in enumerate(calibration_tasks):
        request = InferenceRequest(
            request_id=f"calibrate-crest::{task.task_id}::{i}",
            model=cheap_model_name,
            prompt=task.text,
            system=system_prompt,
            max_output_tokens=policy.max_output_tokens,
            agent_id="benchmark-calibrate",
        )
        result = runtime.infer(request)
        if result.allowed and result.response is not None:
            verdict = score_fn(task, result.response.text)
            ok = bool(verdict["correct"])
        else:
            ok = False
        results[capability_of(task)].append(ok)
        calibration_rows.append(
            {
                "task_id": task.task_id,
                "allowed": result.allowed,
                "correct": ok,
                "attempts": result.attempts,
                "input_tokens": result.input_tokens if result.allowed else 0,
                "output_tokens": result.output_tokens if result.allowed else 0,
            }
        )

    admission = {}
    table_rows = {}
    for capability, checks in results.items():
        n = len(checks)
        if n == 0:
            admission[capability] = False
            table_rows[capability] = {"n": 0, "failures": None, "upper_bound": None, "failures_rate": 0.0}
            continue
        failures = sum(1 for ok in checks if not ok)
        upper = failure_upper_bound_at(failures, n, confidence=0.95)
        admitted = upper <= success_threshold
        admission[capability] = admitted
        table_rows[capability] = {
            "n": n,
            "failures": failures,
            "upper_bound": round(upper, 4),
            "failures_rate": round(failures / n, 4),
        }
    return {
        "admission": admission,
        "calibration_table": table_rows,
        "calibration_rows": calibration_rows,
        "cheap_model": cheap_model_name,
        "large_model": large_model_name,
    }


class CrestRouter:
    """Route pilot/held-out tasks through the calibrated admission table."""

    def __init__(self, admission_table: Mapping[str, bool], small_model: str, large_model: str) -> None:
        self._admission = dict(admission_table)
        self._small = small_model
        self._large = large_model

    def choose_model(self, task: Task) -> str:
        return self._small if self._admission.get(capability_of(task), False) else self._large

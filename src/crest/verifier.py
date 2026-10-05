"""Independent verifier: executes proposed recovery programs and measures.

The verifier is deterministic and does NOT trust the recovery program's
own claims. Evidence comes only from observed execution.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .actions import ACTIONS
from .hashing import digest_of
from .receipts import (
    CapabilityReceipt,
    RecoveryEvidence,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_VERIFIED,
)
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .workspace import Workspace


@dataclass(frozen=True)
class TestConfig:
    trials: int = 20
    repeat_trials: int = 3
    required_success_rate: float = 0.95
    seed: int = 0
    seed_target_content: str | None = None

    def digest(self) -> str:
        return digest_of(
            {
                "trials": self.trials,
                "repeat_trials": self.repeat_trials,
                "required_success_rate": self.required_success_rate,
                "seed": self.seed,
                "seed_target_content": self.seed_target_content,
            }
        )


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(math.ceil(q / 100.0 * len(sorted_vals))) - 1))
    return sorted_vals[idx]


class Verifier:
    VERSION = "sandbox-v1"
    ENVIRONMENT = "sandbox-v1"

    def verify(
        self,
        *,
        action_class: str,
        target_scope: str,
        target: str,
        params: dict[str, Any],
        recovery: RecoveryProgram,
        test_config: TestConfig,
        now: datetime,
        ttl_seconds: float,
    ) -> CapabilityReceipt:
        latencies_ms: list[float] = []
        failures = 0
        max_propagation = 0
        handler = get_handler(recovery.kind)

        if action_class not in ACTIONS:
            return self._failure_receipt(action_class, target_scope, recovery, test_config, now, ttl_seconds, STATUS_ERROR)

        rng = random.Random(test_config.seed)
        total = test_config.trials + test_config.repeat_trials

        for i in range(total):
            repeat = i >= test_config.trials
            ws = Workspace.temporary()
            try:
                target_content = (test_config.seed_target_content or f"seed-{i}-{rng.randrange(10**9)}").encode()
                if action_class not in ("create_file", "create_record"):
                    if action_class in ("create_record", "modify_record", "delete_record"):
                        ws.write(target, b'{"id": 1}')
                    elif action_class == "delete_directory":
                        ws.write(f"{target.rstrip('/')}/f1.txt", target_content)
                        ws.write(f"{target.rstrip('/')}/f2.txt", b"second")
                    else:
                        ws.write(target, target_content)
                for j in range(3):
                    ws.write(f"distractor-{j}.txt", f"d{j}-{i}".encode())
                pre = ws.snapshot()

                try:
                    ACTIONS[action_class](ws, target, _action_params(action_class, target, params))
                except Exception:
                    failures += 1
                    continue

                post_action = ws.snapshot()
                propagation = max(0, len(set(post_action) ^ set(pre)) - 1)
                max_propagation = max(max_propagation, propagation)

                ctx = RecoveryContext(action_class=action_class, target=target, params=params, pre_action_snapshot=pre)
                t0 = time.perf_counter()
                try:
                    if handler is None:
                        raise KeyError(recovery.kind)
                    handler(ws, ctx)
                    if repeat:
                        handler(ws, ctx)
                except Exception:
                    failures += 1
                    continue
                finally:
                    latencies_ms.append((time.perf_counter() - t0) * 1000.0)

                if not ws.state_matches(pre):
                    failures += 1
            finally:
                ws.cleanup()

        test_count = total
        success_rate = (test_count - failures) / test_count if test_count else 0.0
        sorted_lat = sorted(latencies_ms)
        fail_rate = failures / test_count if test_count else 1.0
        residual_ucb = min(1.0, fail_rate + 1.96 * math.sqrt(max(fail_rate * (1 - fail_rate), 1e-9) / max(test_count, 1)))

        evidence = RecoveryEvidence(
            test_count=test_count,
            failed_tests=failures,
            recovery_success_rate=success_rate,
            recovery_latency_p50_ms=_percentile(sorted_lat, 50),
            recovery_latency_p95_ms=_percentile(sorted_lat, 95),
            recovery_latency_p99_ms=_percentile(sorted_lat, 99),
            residual_exposure_ucb=residual_ucb,
            propagation_depth=max_propagation,
            verification_environment=self.ENVIRONMENT,
            verification_version=self.VERSION,
            test_config_digest=test_config.digest(),
            random_seed=test_config.seed,
        )
        status = STATUS_VERIFIED if success_rate >= test_config.required_success_rate else STATUS_FAILED
        return CapabilityReceipt.create(
            action_class=action_class,
            target_scope=target_scope,
            recovery_program_digest=recovery.digest,
            evidence=evidence,
            status=status,
            now=now,
            ttl_seconds=ttl_seconds,
        )

    def _failure_receipt(self, action_class, target_scope, recovery, test_config, now, ttl_seconds, status) -> CapabilityReceipt:
        evidence = RecoveryEvidence(
            test_count=0,
            failed_tests=0,
            recovery_success_rate=0.0,
            recovery_latency_p50_ms=0.0,
            recovery_latency_p95_ms=0.0,
            recovery_latency_p99_ms=0.0,
            residual_exposure_ucb=1.0,
            propagation_depth=0,
            verification_environment=self.ENVIRONMENT,
            verification_version=self.VERSION,
            test_config_digest=test_config.digest(),
            random_seed=test_config.seed,
        )
        return CapabilityReceipt.create(
            action_class=action_class,
            target_scope=target_scope,
            recovery_program_digest=recovery.digest,
            evidence=evidence,
            status=status,
            now=now,
            ttl_seconds=ttl_seconds,
        )


def _action_params(action_class: str, target: str, params: dict[str, Any]) -> dict[str, Any]:
    p = dict(params)
    if action_class == "modify_file" and not p:
        p = {"append": "-modified"}
    if action_class == "move_file" and "destination" not in p:
        p["destination"] = "moved-" + target.rsplit("/", 1)[-1]
    if action_class == "create_record" and "record" not in p:
        p["record"] = {"id": 1}
    if action_class == "modify_record" and "updates" not in p:
        p["updates"] = {"id": 2}
    return p

"""GeneralizationVerifier: evaluates a recovery proposal across fixture
generators, distributions, and a hidden holdout split, producing Evidence
whose class is decided by configurable policy (not by hardcoded rules).

Generators:
  training  crest.fixtures.generate      (fixed-shape synthetic trees)
  holdout   crest.holdout_gen.build      (path-graph construction, independent)

The learner never receives either generator, the shift definitions, or the
holdout seeds.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

from .actions import ACTIONS
from .distributions import Distribution, apply_distribution
from .env_family import FAMILIES, EnvironmentFamily
from .evidence import Evidence, EvidenceClass, EvidenceStatus, failure_upper_bound
from .fixtures import generate as train_generate
from .holdout_gen import build as holdout_build
from .policy import EvidencePolicy
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .workspace import Workspace

VERIFIER_VERSION = "generalization-v2"

SHIFT_DISTRIBUTIONS: tuple[Distribution, ...] = (
    Distribution.PARAMETER_SHIFT,
    Distribution.STRUCTURAL_SHIFT,
    Distribution.ADVERSARIAL_SHIFT,
)


def _trial(action_class: str, family: EnvironmentFamily, recovery: RecoveryProgram, seed: int, distribution: Distribution, use_holdout_generator: bool, params: dict | None = None) -> bool:
    ws = Workspace.temporary()
    try:
        fixture = holdout_build(ws, family, seed) if use_holdout_generator else train_generate(ws, family=family, seed=seed)
        apply_distribution(ws, fixture.target, distribution, seed=seed)
        pre = ws.snapshot()
        target = fixture.target
        action_params = dict(params or {})
        if action_class == "modify_file":
            action_params = {"content": "modified\n"}
        elif action_class == "move_file":
            action_params = {"destination": "moved-" + target.rsplit("/", 1)[-1]}
        try:
            ACTIONS[action_class](ws, target, action_params)
        except Exception:
            return False
        handler = get_handler(recovery.kind)
        if handler is None:
            return False
        try:
            handler(ws, RecoveryContext(action_class, target, action_params, pre))
        except Exception:
            return False
        return ws.state_matches(pre)
    finally:
        ws.cleanup()


class GeneralizationVerifier:
    def __init__(
        self,
        *,
        policy: EvidencePolicy | None = None,
        verification_cases: int = 10,
        holdout_cases: int = 10,
        shift_cases: int = 10,
        verification_seed_base: int = 1000,
        holdout_seed_base: int = 90000,
        shift_seed_base: int = 50000,
    ):
        self.policy = policy or EvidencePolicy()
        self.verification_cases = verification_cases
        self.holdout_cases = holdout_cases
        self.shift_cases = shift_cases
        self.verification_seed_base = verification_seed_base
        self.holdout_seed_base = holdout_seed_base
        self.shift_seed_base = shift_seed_base
        self.last_measurement: dict[str, object] = {}

    # -- measurement ------------------------------------------------------
    def _rate(self, action_class: str, recovery: RecoveryProgram, family: EnvironmentFamily, *, n: int, base: int, distribution: Distribution, holdout_gen: bool, params: dict | None) -> tuple[int, int, float]:
        ok = 0
        t0 = time.perf_counter()
        for i in range(n):
            if _trial(action_class, family, recovery, base + i, distribution, holdout_gen, params):
                ok += 1
        return ok, n, time.perf_counter() - t0

    def verify(
        self,
        *,
        action_class: str,
        recovery: RecoveryProgram,
        family_ids: tuple[str, ...] = ("filesystem.single_file",),
        params: dict | None = None,
    ) -> Evidence:
        families = [FAMILIES[fid] for fid in family_ids]
        handler_available = get_handler(recovery.kind) is not None

        ver_pass = ver_n = 0
        hold_pass = hold_n = 0
        shift_pass = shift_n = 0
        adversarial_pass = adversarial_n = 0
        cost = 0.0

        for fam in families:
            if not handler_available:
                continue
            p, n, s = self._rate(action_class, recovery, fam, n=self.verification_cases, base=self.verification_seed_base, distribution=Distribution.IN_DISTRIBUTION, holdout_gen=False, params=params)
            ver_pass += p; ver_n += n; cost += s
            # Level-2/3 holdout: independent generator, unseen seeds
            p, n, s = self._rate(action_class, recovery, fam, n=self.holdout_cases, base=self.holdout_seed_base, distribution=Distribution.IN_DISTRIBUTION, holdout_gen=True, params=params)
            hold_pass += p; hold_n += n; cost += s
            # distribution shifts on the independent generator
            for d in SHIFT_DISTRIBUTIONS:
                p, n, s = self._rate(action_class, recovery, fam, n=self.shift_cases, base=self.shift_seed_base, distribution=d, holdout_gen=True, params=params)
                shift_pass += p; shift_n += n; cost += s
                if d is Distribution.ADVERSARIAL_SHIFT:
                    adversarial_pass += p; adversarial_n += n

        if not handler_available:
            # no executable recovery program: there is no evidence at all,
            # which is different from "evidence of failure"
            now = datetime.now(timezone.utc)
            return Evidence(
                evidence_id=uuid.uuid4().hex[:16],
                action_class=action_class,
                target_scope="*",
                environment_family=",".join(f.family_id for f in families),
                recovery_program_digest=recovery.digest,
                verification_version=VERIFIER_VERSION,
                verifier_version=VERIFIER_VERSION,
                test_suite_digest="none",
                fixtures_tested=0, fixtures_passed=0, fixtures_failed=0,
                holdout_fixtures=0, holdout_passed=0, holdout_failed=0,
                fault_models_tested=(),
                recovery_success_rate=0.0,
                confidence_level=self.policy.statistics.confidence,
                upper_bound_exposure=1.0,
                propagation_bound=0,
                recovery_time_bound_ms=0.0,
                distribution_shift_failures=0,
                created_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=3600)).isoformat(),
                evidence_class=EvidenceClass.UNVERIFIED,
                status=EvidenceStatus.WEAK,
                sampling_method="none (no executable recovery program)",
                population_scope="none",
            )

        evidence_class, status, diag = self.policy.classify(
            verification_cases=ver_n,
            verification_failures=ver_n - ver_pass,
            holdout_cases=hold_n,
            holdout_failures=hold_n - hold_pass,
            shift_distributions=len(SHIFT_DISTRIBUTIONS) if shift_n else 0,
            shift_failures=shift_n - shift_pass,
            adversarial_checked=adversarial_n > 0,
            adversarial_failures=adversarial_n - adversarial_pass,
            distributions_tested=tuple(d.value for d in SHIFT_DISTRIBUTIONS),
        )
        now = datetime.now(timezone.utc)
        total_pass = ver_pass + hold_pass + shift_pass
        total_n = ver_n + hold_n + shift_n
        evidence = Evidence(
            evidence_id=uuid.uuid4().hex[:16],
            action_class=action_class,
            target_scope="*",
            environment_family=",".join(f.family_id for f in families),
            recovery_program_digest=recovery.digest,
            verification_version=VERIFIER_VERSION,
            verifier_version=VERIFIER_VERSION,
            test_suite_digest=f"ver{self.verification_cases}-hold{self.holdout_cases}-shift{self.shift_cases}x{len(SHIFT_DISTRIBUTIONS)}",
            fixtures_tested=ver_n + hold_n,
            fixtures_passed=ver_pass + hold_pass,
            fixtures_failed=(ver_n - ver_pass) + (hold_n - hold_pass),
            holdout_fixtures=hold_n,
            holdout_passed=hold_pass,
            holdout_failed=hold_n - hold_pass,
            fault_models_tested=tuple(d.value for d in SHIFT_DISTRIBUTIONS),
            recovery_success_rate=round(total_pass / total_n, 6) if total_n else 0.0,
            confidence_level=self.policy.statistics.confidence,
            upper_bound_exposure=failure_upper_bound(total_n - total_pass, total_n),
            propagation_bound=1,
            recovery_time_bound_ms=0.0,
            distribution_shift_failures=shift_n - shift_pass,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=3600)).isoformat(),
            evidence_class=evidence_class,
            status=status,
            sampling_method="train-generator + independent-holdout-generator + shift-distributions",
            population_scope=",".join(f.family_id for f in families),
        )
        self.last_measurement = {
            "verification": {"passed": ver_pass, "n": ver_n},
            "holdout": {"passed": hold_pass, "n": hold_n},
            "shifts": {"passed": shift_pass, "n": shift_n, "distributions": [d.value for d in SHIFT_DISTRIBUTIONS]},
            "adversarial": {"passed": adversarial_pass, "n": adversarial_n},
            "diagnostics": diag,
            "cost_seconds": round(cost, 3),
        }
        return evidence

    def measurement(self) -> dict[str, object]:
        return self.last_measurement
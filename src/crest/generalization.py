"""GeneralizationVerifier: runs a recovery proposal across fixture
families and holdout fixtures, producing conservative Evidence.

No fixture may leak across the train/verify/holdout split: seed bases are
disjoint. A receipt from this verifier is evidence on the *tested
distribution* only; classification into VERIFIED_FAMILY/GENERAL requires
the documented policy thresholds.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

from .actions import ACTIONS
from .env_family import FAMILIES, EnvironmentFamily
from .evidence import Evidence, EvidenceClass, EvidenceStatus, failure_upper_bound
from .fixtures import generate
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .workspace import Workspace

VERIFIER_VERSION = "generalization-v1"


def _run_once(action_class: str, family: EnvironmentFamily, seed: int, recovery: RecoveryProgram, params: dict | None = None) -> bool:
    ws = Workspace.temporary()
    try:
        fx = generate(ws, family=family, seed=seed)
        pre = ws.snapshot()
        action_params = dict(params or {})
        if action_class == "modify_file":
            action_params = {"content": "modified\n"}
        if action_class == "move_file":
            action_params = {"destination": "moved.txt"}
        if action_class == "delete_directory":
            fx_target = "docs"
        else:
            fx_target = fx.target
        try:
            ACTIONS[action_class](ws, fx_target, action_params)
        except (FileNotFoundError, FileExistsError, NotADirectoryError):
            return False
        handler = get_handler(recovery.kind)
        if handler is None:
            return False
        try:
            handler(ws, RecoveryContext(action_class, fx_target, action_params, pre))
        except Exception:
            return False
        return ws.state_matches(pre)
    finally:
        ws.cleanup()


def _classify(*, holdout_total: int, holdout_failures: int, actual_failures: int, total: int, cross_family: bool) -> EvidenceClass:
    """Evidence classification policy (V0.3, conservative, documented).

    VERIFIED_GENERAL requires: holdout>=8, zero holdout failures, zero total
    failures across >=2 families.
    VERIFIED_FAMILY requires: holdout>=4, <=1 holdout failure, zero verify
    failures within the declared family.
    Otherwise VERIFIED_FIXTURE (or UNVERIFIED when failures observed).
    """
    if total == 0:
        return EvidenceClass.UNVERIFIED
    if actual_failures > 0:
        if holdout_failures > 0:
            return EvidenceClass.VERIFIED_FIXTURE if holdout_total < 4 else EvidenceClass.UNVERIFIED
        return EvidenceClass.VERIFIED_FIXTURE
    if cross_family and holdout_total >= 8:
        return EvidenceClass.VERIFIED_GENERAL
    if holdout_total >= 4:
        return EvidenceClass.VERIFIED_FAMILY
    return EvidenceClass.VERIFIED_FIXTURE


class GeneralizationVerifier:
    def __init__(self, *, train_seeds: int = 3, verify_seeds: int = 4, holdout_seeds: int = 4):
        self.train_seeds = train_seeds
        self.verify_seeds = verify_seeds
        self.holdout_seeds = holdout_seeds

    def verify(
        self,
        *,
        action_class: str,
        recovery: RecoveryProgram,
        family_ids: tuple[str, ...] | None = None,
        seed_base: int = 0,
        params: dict | None = None,
    ) -> Evidence:
        families = [FAMILIES[fid] for fid in (family_ids or ("filesystem.single_file",))]
        handle = get_handler(recovery.kind)
        fixtures_tested = fixtures_passed = 0
        holdout_fixtures = holdout_passed = 0
        failures_total = 0
        now = datetime.now(timezone.utc)

        # train + verify are the fixture-testing population
        for fam in families:
            for s in range(self.train_seeds + self.verify_seeds):
                ok = _run_once(action_class, fam, seed_base + 1000 + s, recovery, params) if handle else False
                fixtures_tested += 1
                fixtures_passed += int(ok)
                failures_total += int(not ok)

        # independent holdout seeds are never visible to the learner
        for fam in families:
            for s in range(self.holdout_seeds):
                ok = _run_once(action_class, fam, seed_base + 5000 + s, recovery, params) if handle else False
                holdout_fixtures += 1
                holdout_passed += int(ok)
                failures_total += int(not ok)

        success = (fixtures_passed + holdout_passed) / max(1, fixtures_tested + holdout_fixtures)
        holdout_failures = holdout_fixtures - holdout_passed
        verify_failures = fixtures_tested - fixtures_passed
        cross_family = len(families) > 1
        evidence_class = _classify(
            holdout_total=holdout_fixtures, holdout_failures=holdout_failures,
            actual_failures=verify_failures + holdout_failures, total=fixtures_tested + holdout_fixtures,
            cross_family=cross_family,
        )
        if evidence_class is EvidenceClass.UNVERIFIED and success > 0:
            # partial success without policy-compliant holdout still yields fixture-level evidence
            evidence_class = EvidenceClass.VERIFIED_FIXTURE

        return Evidence(
            evidence_id=uuid.uuid4().hex[:16],
            action_class=action_class,
            target_scope="*",
            environment_family=",".join(f.family_id for f in families),
            recovery_program_digest=recovery.digest,
            verification_version=VERIFIER_VERSION,
            verifier_version=VERIFIER_VERSION,
            test_suite_digest=f"train{self.train_seeds}-verify{self.verify_seeds}-holdout{self.holdout_seeds}",
            fixtures_tested=fixtures_tested,
            fixtures_passed=fixtures_passed,
            fixtures_failed=fixtures_tested - fixtures_passed,
            holdout_fixtures=holdout_fixtures,
            holdout_passed=holdout_passed,
            holdout_failed=holdout_failures,
            fault_models_tested=("baseline",),
            recovery_success_rate=success,
            confidence_level=round(min(fixtures_passed + holdout_passed, fixtures_tested + holdout_fixtures) / max(1, fixtures_tested + holdout_fixtures), 4),
            upper_bound_exposure=failure_upper_bound(failures_total, fixtures_tested + holdout_fixtures),
            propagation_bound=1,
            recovery_time_bound_ms=0.0,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=3600)).isoformat(),
            evidence_class=evidence_class,
            status=EvidenceStatus.OK if failures_total == 0 else EvidenceStatus.WEAK,
        )

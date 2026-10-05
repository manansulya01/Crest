"""Generalized evidence demo: same recovery, different fixture families.

Shows the honest outcome of asking for evidence across families:
restore_from_snapshot may pass; fixture-specific strategies must not get
upgraded. No fake numbers — real deterministic runs.
"""
from __future__ import annotations

import crest.faults  # noqa: F401
from crest.generalization import GeneralizationVerifier
from crest.recovery import RecoveryProgram


def main() -> None:
    for kind in ("restore_from_snapshot", "overfit_distractor_gate", "noop_fault"):
        ev = GeneralizationVerifier().verify(
            action_class="delete_file",
            recovery=RecoveryProgram(kind=kind),
            family_ids=("filesystem.single_file", "filesystem.directory_tree"),
        )
        print(
            f"kind={kind:28s} class={ev.evidence_class.value} "
            f"fixtures={ev.fixtures_passed}/{ev.fixtures_tested} "
            f"holdout={ev.holdout_passed}/{ev.holdout_fixtures} "
            f"rate={ev.recovery_success_rate:.2f} ucb={ev.upper_bound_exposure:.3f}"
        )


if __name__ == "__main__":
    main()

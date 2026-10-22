"""Tests for the validation-only generator and adversarial recovery."""
from __future__ import annotations

from crest.env_family import FAMILIES
from crest.fixtures import generate as training_generate
from crest.holdout_gen import build as holdout_build
from crest.recovery import RecoveryContext, get_handler
from crest.workspace import Workspace
from experiments.validation import generator, recoveries  # noqa: F401


def test_validation_generator_is_deterministic_and_well_formed():
    for family_id in (
        "filesystem.single_file",
        "filesystem.directory_tree",
    ):
        family = FAMILIES[family_id]
        first = Workspace.temporary()
        second = Workspace.temporary()
        try:
            fixture_a = generator.build(first, family, 12345)
            fixture_b = generator.build(second, family, 12345)
            assert fixture_a == fixture_b
            assert fixture_a.target in first.file_set()
            assert fixture_a.file_count == len(first.file_set())
            assert fixture_a.digest == fixture_b.digest
        finally:
            first.cleanup()
            second.cleanup()


def test_validation_generator_is_independent_of_training_and_holdout():
    family = FAMILIES["filesystem.directory_tree"]
    validation = Workspace.temporary()
    training = Workspace.temporary()
    holdout = Workspace.temporary()
    try:
        a = generator.build(validation, family, 777)
        b = training_generate(training, family=family, seed=777)
        c = holdout_build(holdout, family, 777)
        assert a.digest != b.digest
        assert a.digest != c.digest
        assert a.target != b.target
        assert a.target != c.target
    finally:
        validation.cleanup()
        training.cleanup()
        holdout.cleanup()


def test_validation_generator_rejects_unsupported_family():
    ws = Workspace.temporary()
    try:
        try:
            generator.build(ws, FAMILIES["git.repository"], 1)
        except ValueError as exc:
            assert "does not support" in str(exc)
        else:
            raise AssertionError("expected ValueError")
    finally:
        ws.cleanup()


def test_validation_overfit_recovery_needs_training_marker():
    handler = get_handler("validation_overfit_training_shape")
    assert handler is not None

    marked = Workspace.temporary()
    unmarked = Workspace.temporary()
    try:
        marked.write("d0.txt", b"training-marker")
        pre_marked = marked.snapshot()
        marked.write("a.txt", b"changed")
        handler(
            marked,
            RecoveryContext("modify_file", "a.txt", {}, pre_marked),
        )
        assert marked.state_matches(pre_marked)

        unmarked.write("a.txt", b"original")
        pre_unmarked = unmarked.snapshot()
        unmarked.write("a.txt", b"changed")
        handler(
            unmarked,
            RecoveryContext("modify_file", "a.txt", {}, pre_unmarked),
        )
        assert not unmarked.state_matches(pre_unmarked)
    finally:
        marked.cleanup()
        unmarked.cleanup()

"""Canonical experiment configuration: single source of truth.

The V0.5 audit found that ``crest research reproduce --full`` ran at ``n=10``
while the committed tables were generated at ``n=20``, because defaults were
duplicated between experiment modules, the CLI, and the documented
configuration. These tests pin the single source of truth and its agreement
with the modules, the runtime policy defaults, and the CLI.
"""
from __future__ import annotations

import inspect

import pytest
import yaml

from experiments.generalization import (
    ablations,
    confidence_sensitivity,
    config,
    cross_distribution,
    drift_experiment,
    exposure_sweep,
)


@pytest.fixture
def fresh_config():
    yield
    config.canonical.cache_clear()


def _yaml() -> dict:
    return yaml.safe_load(config.CONFIG_PATH.read_text(encoding="utf-8"))


def test_canonical_config_matches_the_declared_yaml():
    raw = _yaml()
    cfg = config.canonical()
    exp = raw["experiments"]
    assert cfg.samples == exp["ablations"]["n_per_measurement"] == 20
    assert cfg.cross_distribution_samples == exp["cross_distribution"]["n_per_distribution"] == 8
    assert cfg.confidence_samples == exp["confidence_sensitivity"]["n_per_measurement"] == 6
    assert cfg.confidence_levels == tuple(exp["confidence_sensitivity"]["levels"])
    assert cfg.confidence_actions == tuple(exp["confidence_sensitivity"]["actions"])
    assert cfg.drift_cases_per_class == exp["drift"]["cases_per_class"] == 3
    assert cfg.maximum_failure_upper_bound == exp["maximum_failure_upper_bound"] == 0.20
    assert list(cfg.actions) == exp["ablations"]["actions"]
    assert list(cfg.families) == exp["ablations"]["families"]
    assert list(cfg.recoveries) == exp["ablations"]["recoveries"]
    assert list(cfg.cross_distribution_recoveries) == exp["cross_distribution"]["recoveries"]
    assert list(cfg.e_max_values) == exp["exposure_sweep"]["e_max_values"]
    assert list(cfg.drift_classes) == exp["drift"]["drift_classes"]
    assert cfg.seed_base == exp["seed_base"]


def test_yaml_documented_policy_matches_runtime_defaults():
    """The documented production policy block cannot silently diverge."""
    from crest.policy import EvidencePolicy

    raw = _yaml()
    base = EvidencePolicy()
    family = raw["evidence"]["family"]
    general = raw["evidence"]["general"]
    stats = raw["statistics"]
    assert base.fixture_requires_exact_scope == raw["evidence"]["fixture"]["requires_exact_scope"]
    assert base.family.minimum_verification_cases == family["minimum_verification_cases"]
    assert base.family.minimum_holdout_cases == family["minimum_holdout_cases"]
    assert base.family.maximum_failure_upper_bound == family["maximum_failure_upper_bound"]
    assert base.general.minimum_holdout_cases == general["minimum_holdout_cases"]
    assert base.general.minimum_shift_distributions == general["minimum_shift_distributions"]
    assert base.general.maximum_failure_upper_bound == general["maximum_failure_upper_bound"]
    assert base.general.require_adversarial_shift == general["require_adversarial_shift"]
    assert base.statistics.confidence == stats["confidence"]
    assert base.statistics.minimum_samples_family == stats["minimum_samples"]["family"]
    assert base.statistics.minimum_samples_general == stats["minimum_samples"]["general"]


def test_module_defaults_resolve_to_the_canonical_configuration():
    cfg = config.canonical()
    assert inspect.signature(ablations.run_all).parameters["n"].default is None
    assert inspect.signature(ablations.evaluate_mode).parameters["n"].default is None
    assert inspect.signature(ablations._policy_for_mode).parameters["n"].default is None
    assert inspect.signature(cross_distribution.run_grid).parameters["samples"].default is None
    assert inspect.signature(cross_distribution.measure).parameters["train_n"].default is None
    assert inspect.signature(confidence_sensitivity.evaluate).parameters["n"].default is None
    assert inspect.signature(confidence_sensitivity.run_all).parameters["n"].default is None
    assert inspect.signature(drift_experiment.run).parameters["cases"].default is None
    assert inspect.signature(exposure_sweep.run_all).parameters["budgets"].default is None

    # Module constants mirror the canonical values (documentation, not
    # competing defaults: None means "canonical", these only record it).
    assert ablations.RECOVERIES == cfg.recoveries
    assert confidence_sensitivity.CONFIDENCES == cfg.confidence_levels
    assert confidence_sensitivity.FAMILIES_TESTED == cfg.families
    assert confidence_sensitivity.RECOVERIES == cfg.recoveries


def test_scaled_experimental_policy_resolves_to_canonical_samples():
    cfg = config.canonical()
    resolved = ablations._policy_for_mode("family_evidence")
    explicit = ablations._policy_for_mode("family_evidence", cfg.samples)
    assert resolved == explicit
    assert resolved.family.minimum_holdout_cases == cfg.samples
    assert resolved.family.minimum_verification_cases == cfg.samples
    assert resolved.family.maximum_failure_upper_bound == cfg.maximum_failure_upper_bound
    assert resolved.statistics.minimum_samples_family == 2 * cfg.samples
    assert resolved.statistics.minimum_samples_general == 2 * cfg.samples


def test_cross_distribution_measure_resolves_every_sample_to_canonical(monkeypatch):
    cfg = config.canonical()
    calls: list[int] = []

    def fake_trial(action_class, recovery, builder, family_id, seed, distribution, params=None):
        calls.append(seed)
        return True

    monkeypatch.setattr(cross_distribution, "_trial", fake_trial)
    metrics = cross_distribution.measure(
        "delete_file", "filesystem.single_file", "restore_from_snapshot"
    )
    assert all(metric["n"] == cfg.cross_distribution_samples for metric in metrics.values())
    # 8 metrics: 5 at n samples + 3 shifts at n samples
    assert len(calls) == 8 * cfg.cross_distribution_samples


def test_config_digest_is_stable_and_sensitive(tmp_path, monkeypatch, fresh_config):
    cfg = config.canonical()
    assert cfg.digest() == config.canonical().digest()
    assert cfg.digest() == config.reload().digest()

    text = config.CONFIG_PATH.read_text(encoding="utf-8")

    # Comments and formatting do not change the normalized digest.
    comment_only = tmp_path / "comment.yaml"
    comment_only.write_text(text + "\n# a trailing comment\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", comment_only)
    assert config.reload().digest() == cfg.digest()

    # A meaningful parameter change does.
    raw = yaml.safe_load(text)
    raw["experiments"]["ablations"]["n_per_measurement"] = cfg.samples + 1
    changed_path = tmp_path / "changed.yaml"
    changed_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", changed_path)
    changed = config.reload()
    assert changed.samples == cfg.samples + 1
    assert changed.digest() != cfg.digest()


def test_missing_configuration_raises_explicitly(tmp_path, monkeypatch, fresh_config):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "absent.yaml")
    with pytest.raises(config.ExperimentConfigError):
        config.reload()


def test_cli_reproduce_help_documents_modes_and_overrides(capsys):
    import crest.cli as cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["research", "reproduce", "--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--full" in out
    assert "--samples" in out
    assert "canonical" in out


def test_cli_rejects_non_positive_sample_override(capsys):
    import crest.cli as cli

    assert cli.main(["research", "reproduce", "--samples", "0"]) == 2
    assert "--samples" in capsys.readouterr().err
    assert cli.main(["research", "reproduce", "--samples", "-3"]) == 2

"""Authoritative experiment configuration for the reported research artifacts.

``experiments/configs/experiment.yaml`` is the canonical declaration of the
parameters under which the committed research artifacts were produced. Every
experiment module, the CLI, and the tests resolve their parameters through
this module so that a parameter cannot silently diverge between them (the
V0.5 audit found the CLI reproducing at ``n=10`` while the committed tables
were generated at ``n=20`` precisely because defaults were duplicated).

Canonical here is a *provenance* claim: these are the parameters the
published artifacts were produced with. It is not a claim that they are
scientifically optimal.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "experiment.yaml"


class ExperimentConfigError(RuntimeError):
    """The canonical experiment configuration is missing or invalid."""


@dataclass(frozen=True)
class CanonicalConfig:
    """Canonical parameters of the V0.4 research artifacts."""

    config_version: int
    samples: int
    maximum_failure_upper_bound: float
    seed_base: int
    actions: tuple[str, ...]
    families: tuple[str, ...]
    recoveries: tuple[str, ...]
    cross_distribution_samples: int
    cross_distribution_recoveries: tuple[str, ...]
    confidence_levels: tuple[float, ...]
    confidence_samples: int
    confidence_actions: tuple[str, ...]
    e_max_values: tuple[float, ...]
    drift_classes: tuple[str, ...]
    drift_cases_per_class: int

    def as_dict(self) -> dict[str, Any]:
        """Normalized, JSON-serializable view used for digests and manifests."""
        return {
            "config_version": self.config_version,
            "samples": self.samples,
            "maximum_failure_upper_bound": self.maximum_failure_upper_bound,
            "seed_base": self.seed_base,
            "actions": list(self.actions),
            "families": list(self.families),
            "recoveries": list(self.recoveries),
            "cross_distribution": {
                "samples": self.cross_distribution_samples,
                "recoveries": list(self.cross_distribution_recoveries),
            },
            "confidence_sensitivity": {
                "levels": list(self.confidence_levels),
                "samples": self.confidence_samples,
                "actions": list(self.confidence_actions),
            },
            "exposure_sweep": {"e_max_values": list(self.e_max_values)},
            "drift": {
                "classes": list(self.drift_classes),
                "cases_per_class": self.drift_cases_per_class,
            },
        }

    def digest(self) -> str:
        """SHA-256 over the normalized canonical configuration.

        Covers every parameter that materially affects the reported
        experiments; changes to the config file that do not alter these
        parameters (comments, ordering of unrelated keys) do not change it.
        """
        payload = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _load() -> CanonicalConfig:
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExperimentConfigError(
            f"cannot read canonical experiment configuration {CONFIG_PATH}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ExperimentConfigError(
            f"cannot parse canonical experiment configuration {CONFIG_PATH}: {exc}"
        ) from exc

    experiments = (raw or {}).get("experiments") or {}
    ablations = experiments.get("ablations") or {}
    cross = experiments.get("cross_distribution") or {}
    confidence = experiments.get("confidence_sensitivity") or {}
    sweep = experiments.get("exposure_sweep") or {}
    drift = experiments.get("drift") or {}

    try:
        config = CanonicalConfig(
            config_version=int(raw.get("config_version", 1)),
            samples=int(ablations["n_per_measurement"]),
            maximum_failure_upper_bound=float(
                experiments["maximum_failure_upper_bound"]
            ),
            seed_base=int(experiments.get("seed_base", 0)),
            actions=tuple(ablations["actions"]),
            families=tuple(ablations["families"]),
            recoveries=tuple(ablations["recoveries"]),
            cross_distribution_samples=int(cross["n_per_distribution"]),
            cross_distribution_recoveries=tuple(cross["recoveries"]),
            confidence_levels=tuple(
                float(level) for level in confidence["levels"]
            ),
            confidence_samples=int(confidence["n_per_measurement"]),
            confidence_actions=tuple(confidence["actions"]),
            e_max_values=tuple(float(v) for v in sweep["e_max_values"]),
            drift_classes=tuple(drift["drift_classes"]),
            drift_cases_per_class=int(drift["cases_per_class"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExperimentConfigError(
            f"canonical experiment configuration {CONFIG_PATH} is incomplete "
            f"or malformed: {exc}"
        ) from exc

    if config.samples <= 0 or config.cross_distribution_samples <= 0 or config.confidence_samples <= 0:
        raise ExperimentConfigError(
            f"canonical experiment configuration {CONFIG_PATH} has non-positive "
            "sample counts"
        )
    if not 0 < config.maximum_failure_upper_bound <= 1:
        raise ExperimentConfigError(
            f"canonical experiment configuration {CONFIG_PATH} has an invalid "
            "maximum_failure_upper_bound"
        )
    return config


@lru_cache(maxsize=1)
def canonical() -> CanonicalConfig:
    """Return the canonical configuration (parsed once)."""
    return _load()


def reload() -> CanonicalConfig:
    """Clear the cache and re-read the configuration file."""
    canonical.cache_clear()
    return canonical()

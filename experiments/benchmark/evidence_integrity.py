"""Evidence Integrity experiment — Cycle 3.

Non-circular simulator for evidence aggregation with explicit provenance,
dependency structure, claim scope, and risk-dependent sufficiency decisions.

World model
-----------
A task contains a claim with ``n_subclaims`` required subclaims.  The claim is
true iff every required subclaim is true.  A cheap generator produces the claim;
hidden difficulty controls how often each subclaim is wrong.

Evidence channels (simulated cost units, not currency):

  det_rule      deterministic check of subclaim 0 (numeric).  Applicable with
                probability ``det_applicable_rate``; when applicable it is
                always correct.  Its weakness is scope, not reliability.
  cheap_judge   LLM judge covering both subclaims.  Accuracy depends on the
                hidden quality of its source family.
  strong_judge  stronger LLM judge.  Shares the cheap judge's source family with
                probability ``share_p`` (common-cause failure).
  ext_registry  external source covering subclaim 1 (factual), independent of
                the judge families, accuracy ``ext_accuracy``.
  format_check  out-of-scope check (scope = extra subclaim index).  It passes
                but says nothing about the required subclaims.  Naive policies
                count it; scope-aware policies ignore it.
  duplicate     exact copy of the cheap judge (same source, same verdicts,
                different evidence id).  Naive policies count it twice.

Provenance
----------
Every item has an ancestry tuple (source family) or ``None`` for unknown
provenance.  ``unk_rate`` drops ancestry metadata.  ``false_prov_rate`` replaces
ancestry with unique fake families (adversarial metadata; the policy cannot
detect the forgery).  Evidence from one ancestry cluster contributes at most one
independent unit of support.  Unknown-provenance items are pooled into a single
weak cluster and are never treated as independent.

Policies see verdicts, scope, ancestry metadata (or UNKNOWN), risk class, and
calibrated priors.  They never see latent difficulty, ground-truth correctness,
subclaim correctness, or family quality.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    n_subclaims: int = 2
    base_fail: Tuple[float, ...] = (0.05, 0.10)
    difficulty_slope: Tuple[float, ...] = (0.35, 0.25)
    family_good_prob: float = 0.70
    judge_acc_good: float = 0.85       # cheap judge, good family
    judge_acc_bad: float = 0.15        # cheap judge, bad family
    strong_acc_good: float = 0.95      # strong judge, good family
    strong_acc_bad: float = 0.05       # strong judge, bad family
    share_p: float = 0.70
    ext_accuracy: float = 0.85
    det_applicable_rate: float = 0.45
    ext_available_rate: float = 0.60
    unk_rate: float = 0.30
    false_prov_rate: float = 0.0
    stale_rate: float = 0.0
    dup_copies: int = 1
    include_distractor: bool = True
    costs: Dict[str, float] = field(default_factory=lambda: {
        "det_rule": 0.02,
        "cheap_judge": 0.50,
        "strong_judge": 2.00,
        "ext_registry": 0.80,
        "format_check": 0.05,
    })
    # Risk-dependent assurance thresholds (pre-registered, not fitted to results).
    accept_threshold: Dict[str, float] = field(default_factory=lambda: {
        "low": 0.85, "med": 0.92, "high": 0.98,
    })
    reject_threshold: Dict[str, float] = field(default_factory=lambda: {
        "low": 0.15, "med": 0.08, "high": 0.03,
    })
    budget: Dict[str, float] = field(default_factory=lambda: {
        "low": 2.50, "med": 3.50, "high": 4.00,
    })
    # Ex-post risk-weighted loss (evaluation only; policies do not optimise this).
    loss_fa: Dict[str, float] = field(default_factory=lambda: {
        "low": 4.0, "med": 12.0, "high": 50.0,
    })
    loss_fr: Dict[str, float] = field(default_factory=lambda: {
        "low": 2.0, "med": 4.0, "high": 8.0,
    })
    loss_indet: Dict[str, float] = field(default_factory=lambda: {
        "low": 1.0, "med": 1.5, "high": 2.0,
    })


DEFAULT_CONFIG = Config()


def stable_seed(*parts: object) -> int:
    """Process-independent seed derived from SHA-256 (never Python hash())."""
    text = "::".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _rng(*parts: object) -> random.Random:
    return random.Random(stable_seed(*parts))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    kind: str
    family: str
    ancestry: Optional[Tuple[str, ...]]      # None => unknown provenance
    scope: Tuple[int, ...]                   # subclaim indices this item covers
    verdicts: Tuple[Optional[bool], ...]     # aligned with scope; True=support
    cost: float
    stale: bool = False

    def covers(self, subclaim: int) -> bool:
        return subclaim in self.scope

    def verdict_for(self, subclaim: int) -> Optional[bool]:
        if subclaim not in self.scope:
            return None
        return self.verdicts[self.scope.index(subclaim)]

    def has_signal(self) -> bool:
        return any(v is not None for v in self.verdicts)


@dataclass
class Task:
    task_id: str
    seed: int
    split: str
    risk: str
    difficulty: float
    subclaim_correct: Tuple[bool, ...]
    det_applicable: bool
    ext_available: bool
    evidence: List[EvidenceItem] = field(default_factory=list)

    @property
    def truth(self) -> bool:
        return all(self.subclaim_correct)


def _make_item(
    task_id: str,
    seed: int,
    index: int,
    kind: str,
    family: str,
    scope: Tuple[int, ...],
    verdicts: Tuple[Optional[bool], ...],
    cost: float,
    config: Config,
    ancestry_override: Optional[Tuple[str, ...]] = None,
    stale_override: Optional[bool] = None,
) -> EvidenceItem:
    """Build one item with deterministic ancestry/staleness metadata."""
    if ancestry_override is not None:
        ancestry = ancestry_override
    elif _rng("unk", task_id, kind).random() < config.unk_rate:
        ancestry = None
    else:
        ancestry = (family,)
    if config.false_prov_rate > 0.0 and _rng(
        "falseprov", task_id, kind
    ).random() < config.false_prov_rate:
        ancestry = ("fake", task_id, kind)
    stale = (
        stale_override
        if stale_override is not None
        else _rng("stale", task_id, kind).random() < config.stale_rate
    )
    return EvidenceItem(
        evidence_id=f"{task_id}:{kind}:{index}",
        kind=kind,
        family=family,
        ancestry=ancestry,
        scope=scope,
        verdicts=verdicts,
        cost=cost,
        stale=stale,
    )


def generate_tasks(
    n_calibration: int,
    n_evaluation: int,
    seed: int,
    config: Config = DEFAULT_CONFIG,
) -> Tuple[List[Task], List[Task]]:
    """Generate disjoint calibration and evaluation splits deterministically."""
    if len(config.base_fail) < config.n_subclaims:
        raise ValueError("base_fail must cover every required subclaim")
    if len(config.difficulty_slope) < config.n_subclaims:
        raise ValueError("difficulty_slope must cover every required subclaim")

    tasks: List[Task] = []
    total = n_calibration + n_evaluation
    for i in range(total):
        split = "calibration" if i < n_calibration else "evaluation"
        task_id = f"ei-{split}-{seed}-{i:05d}"
        rng = _rng("task", seed, i)

        difficulty = rng.random()
        risk_roll = rng.random()
        risk = "high" if risk_roll > 0.80 else ("med" if risk_roll > 0.50 else "low")

        subclaim_correct = tuple(
            rng.random() > (config.base_fail[j] + config.difficulty_slope[j] * difficulty)
            for j in range(config.n_subclaims)
        )

        shared = rng.random() < config.share_p
        cheap_family = "llm_cheap"
        strong_family = cheap_family if shared else "llm_strong"
        family_quality: Dict[str, bool] = {}
        families = [cheap_family]
        if strong_family != cheap_family:
            families.append(strong_family)
        for family in families:
            family_quality[family] = rng.random() < config.family_good_prob

        det_applicable = rng.random() < config.det_applicable_rate
        ext_available = rng.random() < config.ext_available_rate

        evidence: List[EvidenceItem] = []

        # Deterministic check on the numeric subclaim (index 0).
        det_scope = (0,)
        det_verdicts: Tuple[Optional[bool], ...] = (
            (subclaim_correct[0],) if det_applicable else (None,)
        )
        evidence.append(_make_item(
            task_id, seed, 0, "det_rule", "rule", det_scope, det_verdicts,
            config.costs["det_rule"], config,
        ))

        # Cheap and strong judges cover every required subclaim.
        judge_scope = tuple(range(config.n_subclaims))

        def judge_verdicts(family: str, kind: str) -> Tuple[bool, ...]:
            quality = family_quality[family]
            if kind == "strong_judge":
                acc = config.strong_acc_good if quality else config.strong_acc_bad
            else:
                acc = config.judge_acc_good if quality else config.judge_acc_bad
            out = []
            for j in judge_scope:
                accurate = _rng("judge", seed, i, kind, family, j).random() < acc
                out.append(subclaim_correct[j] if accurate else not subclaim_correct[j])
            return tuple(out)

        cheap_verdicts = judge_verdicts(cheap_family, "cheap_judge")
        strong_verdicts = judge_verdicts(strong_family, "strong_judge")

        # External registry covers the factual subclaim (index 1 when present).
        ext_scope = (1 if config.n_subclaims > 1 else 0,)
        if ext_available:
            ext_acc = config.ext_accuracy
            accurate = _rng("ext", seed, i).random() < ext_acc
            j = ext_scope[0]
            ext_verdicts: Tuple[Optional[bool], ...] = (
                subclaim_correct[j] if accurate else not subclaim_correct[j],
            )
        else:
            ext_verdicts = (None,)

        # Out-of-scope format check: passes, but concerns an extra property.
        extra_index = config.n_subclaims
        format_scope = (extra_index,)
        format_verdicts: Tuple[Optional[bool], ...] = (True,)

        # Ancestry is computed once for the cheap judge so its duplicate inherits
        # the same (possibly unknown or forged) lineage metadata.
        cheap_item = _make_item(
            task_id, seed, 1, "cheap_judge", cheap_family, judge_scope,
            cheap_verdicts, config.costs["cheap_judge"], config,
        )
        strong_item = _make_item(
            task_id, seed, 2, "strong_judge", strong_family, judge_scope,
            strong_verdicts, config.costs["strong_judge"], config,
        )
        ext_item = _make_item(
            task_id, seed, 3, "ext_registry", "registry", ext_scope,
            ext_verdicts, config.costs["ext_registry"], config,
        )
        evidence.extend([cheap_item, strong_item, ext_item])

        if config.include_distractor:
            evidence.append(_make_item(
                task_id, seed, 4, "format_check", "format", format_scope,
                format_verdicts, config.costs["format_check"], config,
            ))

        for copy_index in range(config.dup_copies):
            evidence.append(_make_item(
                task_id, seed, 100 + copy_index, "cheap_judge", cheap_family,
                judge_scope, cheap_verdicts, config.costs["cheap_judge"], config,
                ancestry_override=cheap_item.ancestry,
                stale_override=cheap_item.stale,
            ))

        tasks.append(Task(
            task_id=task_id,
            seed=seed,
            split=split,
            risk=risk,
            difficulty=difficulty,
            subclaim_correct=subclaim_correct,
            det_applicable=det_applicable,
            ext_available=ext_available,
            evidence=evidence,
        ))

    calibration = [t for t in tasks if t.split == "calibration"]
    evaluation = [t for t in tasks if t.split == "evaluation"]
    return calibration, evaluation


# ---------------------------------------------------------------------------
# Calibration (uses labels on the calibration split only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Calibration:
    prior_subclaim: float
    rel_det: float
    rel_cheap: float
    rel_strong: float
    rel_ext: float
    rel_format: float = 0.60
    rel_unknown: float = 0.50


def calibrate(tasks: Sequence[Task], config: Config) -> Calibration:
    """Estimate priors and per-kind reliability from labelled calibration tasks.

    Ground-truth labels are used here only, never during evaluation.  Laplace
    smoothing prevents degenerate 0/1 estimates from small samples.
    """
    correct = 0
    total = 0
    counts: Dict[str, List[int]] = {
        "det_rule": [0, 0],
        "cheap_judge": [0, 0],
        "strong_judge": [0, 0],
        "ext_registry": [0, 0],
        "format_check": [0, 0],
    }
    for task in tasks:
        for value in task.subclaim_correct:
            correct += int(value)
            total += 1
        for item in task.evidence:
            if item.stale or item.ancestry is None:
                continue
            group = item.kind
            if group not in counts:
                continue
            for j in item.scope:
                if j >= config.n_subclaims:
                    continue
                verdict = item.verdict_for(j)
                if verdict is None:
                    continue
                counts[group][0] += int(verdict == task.subclaim_correct[j])
                counts[group][1] += 1

    def reliability(group: str) -> float:
        successes, n = counts[group]
        return (successes + 1.0) / (n + 2.0) if n else 0.50

    return Calibration(
        prior_subclaim=(correct + 1.0) / (total + 2.0) if total else 0.50,
        rel_det=reliability("det_rule"),
        rel_cheap=reliability("cheap_judge"),
        rel_strong=reliability("strong_judge"),
        rel_ext=reliability("ext_registry"),
        rel_format=0.60,
        rel_unknown=0.50,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _clamp_probability(value: float) -> float:
    return min(max(value, 1e-6), 1.0 - 1e-6)


def _item_reliability(item: EvidenceItem, calibration: Calibration) -> float:
    if item.ancestry is None:
        # Unknown provenance is capped: it can never act as strong evidence.
        base = min(calibration.rel_unknown, 0.50)
    elif item.kind == "det_rule":
        base = calibration.rel_det
    elif item.kind == "cheap_judge":
        base = calibration.rel_cheap
    elif item.kind == "strong_judge":
        base = calibration.rel_strong
    elif item.kind == "ext_registry":
        base = calibration.rel_ext
    elif item.kind == "format_check":
        base = calibration.rel_format
    else:
        base = 0.60
    if item.stale:
        base = min(base, 0.50)
    return _clamp_probability(base)


def _cluster_key(item: EvidenceItem) -> Tuple[str, ...]:
    if item.ancestry is None:
        # Every unknown-provenance item is pooled into one weak cluster.  This
        # is the rule that prevents unknown independence from becoming assumed
        # independence.
        return ("unknown",)
    return ("known",) + tuple(item.ancestry)


def _verdict_for(
    item: EvidenceItem, subclaim: int, scope_aware: bool
) -> Optional[bool]:
    if item.covers(subclaim):
        verdict = item.verdict_for(subclaim)
        if verdict is not None:
            return verdict
    if scope_aware:
        return None
    # Scope-blind policies reuse whatever signal the item carries, even when it
    # concerns a different property.  This is the naive baseline.
    for verdict in item.verdicts:
        if verdict is not None:
            return verdict
    return None


def _majority(verdicts: Sequence[bool]) -> Optional[bool]:
    supports = sum(1 for v in verdicts if v is True)
    refutes = sum(1 for v in verdicts if v is False)
    if supports > refutes:
        return True
    if refutes > supports:
        return False
    return None


def subclaim_confidence(
    items: Sequence[EvidenceItem],
    subclaim: int,
    calibration: Calibration,
    *,
    blind: bool,
    scope_aware: bool,
) -> float:
    """Posterior P(subclaim correct | evidence) under a cluster model.

    blind=True        every item is an independent unit (duplicates count).
    blind=False       one unit per ancestry cluster; unknown items share one
                      capped cluster.
    scope_aware=False out-of-scope items are counted as if they applied.
    """
    groups: Dict[Tuple[str, ...], List[Tuple[EvidenceItem, bool]]] = {}
    for item in items:
        verdict = _verdict_for(item, subclaim, scope_aware)
        if verdict is None:
            continue
        key = ("item", item.evidence_id) if blind else _cluster_key(item)
        groups.setdefault(key, []).append((item, verdict))

    prior = _clamp_probability(calibration.prior_subclaim)
    log_odds = math.log(prior / (1.0 - prior))
    for pairs in groups.values():
        cluster_verdict = _majority([v for _, v in pairs])
        if cluster_verdict is None:
            continue
        reliability = max(_item_reliability(item, calibration) for item, _ in pairs)
        delta = math.log(reliability / (1.0 - reliability))
        log_odds += delta if cluster_verdict else -delta
    return 1.0 / (1.0 + math.exp(-log_odds))


def claim_confidence(
    items: Sequence[EvidenceItem],
    calibration: Calibration,
    config: Config,
    *,
    blind: bool,
    scope_aware: bool,
) -> Tuple[float, Tuple[float, ...]]:
    """Weakest-link claim confidence: every required subclaim must be supported."""
    per_subclaim = tuple(
        subclaim_confidence(
            items, j, calibration, blind=blind, scope_aware=scope_aware
        )
        for j in range(config.n_subclaims)
    )
    return min(per_subclaim), per_subclaim


def decide(confidence: float, risk: str, config: Config) -> str:
    if confidence >= config.accept_threshold[risk]:
        return "ACCEPT"
    if confidence <= config.reject_threshold[risk]:
        return "REJECT"
    return "INDETERMINATE"


# ---------------------------------------------------------------------------
# Policy results
# ---------------------------------------------------------------------------


@dataclass
class PolicyResult:
    decision: str
    cost: float
    acquisitions: int
    confidence: float
    evidence_ids: Tuple[str, ...]
    per_subclaim: Tuple[float, ...] = ()


def _usable(task: Task) -> List[EvidenceItem]:
    return [item for item in task.evidence if item.has_signal()]


def _result(
    decision: str,
    items: Sequence[EvidenceItem],
    confidence: float,
    per_subclaim: Tuple[float, ...] = (),
) -> PolicyResult:
    return PolicyResult(
        decision=decision,
        cost=sum(item.cost for item in items),
        acquisitions=len(items),
        confidence=confidence,
        evidence_ids=tuple(item.evidence_id for item in items),
        per_subclaim=per_subclaim,
    )


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def _first(task: Task, kind: str) -> Optional[EvidenceItem]:
    return next((item for item in task.evidence if item.kind == kind), None)


def _supports_required(item: EvidenceItem, config: Config) -> Optional[bool]:
    """True/False if the item speaks to every required subclaim, else None."""
    verdicts = []
    for j in range(config.n_subclaims):
        verdict = item.verdict_for(j)
        if verdict is None:
            return None
        verdicts.append(verdict)
    return all(verdicts)


def policy_no_verify(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    return _result("ACCEPT", [], calibration.prior_subclaim)


def policy_single_det(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    item = _first(task, "det_rule")
    if item is None or not item.has_signal():
        return _result("ACCEPT", [], calibration.prior_subclaim)
    verdict = item.verdict_for(0)
    decision = "ACCEPT" if verdict else "REJECT"
    confidence = 0.99 if verdict else 0.01
    return _result(decision, [item], confidence)


def policy_single_cheap(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    item = _first(task, "cheap_judge")
    if item is None:
        return _result("INDETERMINATE", [], calibration.prior_subclaim)
    supported = _supports_required(item, config)
    if supported is True:
        decision = "ACCEPT"
    elif supported is False:
        decision = "REJECT"
    else:
        decision = "INDETERMINATE"
    confidence, per = claim_confidence(
        [item], calibration, config, blind=True, scope_aware=True
    )
    return _result(decision, [item], confidence, per)


def policy_single_strong(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    item = _first(task, "strong_judge")
    if item is None:
        return _result("INDETERMINATE", [], calibration.prior_subclaim)
    supported = _supports_required(item, config)
    if supported is True:
        decision = "ACCEPT"
    elif supported is False:
        decision = "REJECT"
    else:
        decision = "INDETERMINATE"
    confidence, per = claim_confidence(
        [item], calibration, config, blind=True, scope_aware=True
    )
    return _result(decision, [item], confidence, per)


def _first_signal(item: EvidenceItem) -> Optional[bool]:
    for verdict in item.verdicts:
        if verdict is not None:
            return verdict
    return None


def policy_majority_vote(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    items = _usable(task)
    verdicts = [v for v in (_first_signal(item) for item in items) if v is not None]
    supports = sum(1 for v in verdicts if v is True)
    refutes = sum(1 for v in verdicts if v is False)
    if supports > refutes:
        decision = "ACCEPT"
    elif refutes > supports:
        decision = "REJECT"
    else:
        decision = "INDETERMINATE"
    confidence = supports / (supports + refutes) if supports + refutes else 0.5
    return _result(decision, items, confidence)


def policy_naive_count(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    items = _usable(task)
    verdicts = [v for v in (_first_signal(item) for item in items) if v is not None]
    supports = sum(1 for v in verdicts if v is True)
    refutes = sum(1 for v in verdicts if v is False)
    if supports >= 3:
        decision = "ACCEPT"
    elif supports == 0 and refutes > 0:
        decision = "REJECT"
    else:
        decision = "INDETERMINATE"
    confidence = supports / (supports + refutes) if supports + refutes else 0.5
    return _result(decision, items, confidence)


def policy_fixed_cascade(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    cheap = _first(task, "cheap_judge")
    strong = _first(task, "strong_judge")
    if cheap is None:
        return _result("ACCEPT", [], calibration.prior_subclaim)
    supported = _supports_required(cheap, config)
    if supported is True:
        return _result("ACCEPT", [cheap], 0.90)
    if strong is None:
        return _result("REJECT", [cheap], 0.10)
    strong_supported = _supports_required(strong, config)
    items = [cheap, strong]
    if strong_supported is True:
        return _result("ACCEPT", items, 0.95)
    return _result("REJECT", items, 0.05)


def policy_blind_bayes(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    items = _usable(task)
    confidence, per = claim_confidence(
        items, calibration, config, blind=True, scope_aware=False
    )
    return _result(decide(confidence, task.risk, config), items, confidence, per)


def policy_provenance_aware(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    items = _usable(task)
    confidence, per = claim_confidence(
        items, calibration, config, blind=False, scope_aware=True
    )
    return _result(decide(confidence, task.risk, config), items, confidence, per)


def _sequential_order(task: Task, *, blind: bool) -> List[EvidenceItem]:
    if blind:
        # Naive acquisition: cheapest first, so duplicate and out-of-scope
        # evidence are purchased early and counted as independent.
        order = [
            item for item in task.evidence
            if item.has_signal()
        ]
        order.sort(key=lambda item: (item.cost, item.evidence_id))
        return order

    # Provenance-aware acquisition: diversify source kinds before repeating a
    # kind, and defer duplicates.  Unknown-provenance duplicates cannot be
    # identified in advance, so they remain in the deferred group.
    kinds = ["det_rule", "cheap_judge", "ext_registry", "strong_judge"]
    primary: List[EvidenceItem] = []
    extras: List[EvidenceItem] = []
    for kind in kinds:
        items = [
            item for item in task.evidence
            if item.kind == kind and item.has_signal()
        ]
        items.sort(key=lambda item: item.evidence_id)
        if items:
            primary.append(items[0])
            extras.extend(items[1:])
    extras.sort(key=lambda item: (item.cost, item.evidence_id))
    return primary + extras


def _is_redundant(item: EvidenceItem, acquired: Sequence[EvidenceItem]) -> bool:
    """Known-provenance duplicate of a source already represented at equal scope."""
    if item.ancestry is None:
        return False
    for prior in acquired:
        if prior.ancestry == item.ancestry and set(item.scope).issubset(set(prior.scope)):
            return True
    return False


def _run_sequential(
    task: Task,
    calibration: Calibration,
    config: Config,
    *,
    blind: bool,
    scope_aware: bool,
    order: Sequence[EvidenceItem],
) -> PolicyResult:
    acquired: List[EvidenceItem] = []
    cost = 0.0
    budget = config.budget[task.risk]
    accept_at = config.accept_threshold[task.risk]
    reject_at = config.reject_threshold[task.risk]

    for item in order:
        if cost + item.cost > budget + 1e-9:
            continue
        if not blind and _is_redundant(item, acquired):
            continue
        acquired.append(item)
        cost += item.cost
        confidence, per = claim_confidence(
            acquired, calibration, config, blind=blind, scope_aware=scope_aware
        )
        if confidence >= accept_at:
            return _result("ACCEPT", acquired, confidence, per)
        if confidence <= reject_at:
            return _result("REJECT", acquired, confidence, per)

    confidence, per = claim_confidence(
        acquired, calibration, config, blind=blind, scope_aware=scope_aware
    )
    return _result(decide(confidence, task.risk, config), acquired, confidence, per)


def policy_blind_sequential(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    order = _sequential_order(task, blind=True)
    return _run_sequential(
        task, calibration, config, blind=True, scope_aware=False, order=order
    )


def policy_provenance_sequential(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    order = _sequential_order(task, blind=False)
    return _run_sequential(
        task, calibration, config, blind=False, scope_aware=True, order=order
    )


def _strong_first_order(task: Task) -> List[EvidenceItem]:
    """Cascade-shaped acquisition: cheap, then strong, then independent sources."""
    kinds = ["cheap_judge", "strong_judge", "ext_registry", "det_rule"]
    primary: List[EvidenceItem] = []
    extras: List[EvidenceItem] = []
    for kind in kinds:
        items = [
            item for item in task.evidence
            if item.kind == kind and item.has_signal()
        ]
        items.sort(key=lambda item: item.evidence_id)
        if items:
            primary.append(items[0])
            extras.extend(items[1:])
    extras.sort(key=lambda item: (item.cost, item.evidence_id))
    return primary + extras


def policy_provenance_sequential_strong_first(
    task: Task, calibration: Calibration, config: Config
) -> PolicyResult:
    return _run_sequential(
        task, calibration, config, blind=False, scope_aware=True,
        order=_strong_first_order(task),
    )


def _integrity_evidence(task: Task) -> List[EvidenceItem]:
    """In-scope, first-of-kind evidence only; duplicates and format checks omitted."""
    items: List[EvidenceItem] = []
    for kind in ("det_rule", "cheap_judge", "ext_registry", "strong_judge"):
        item = _first(task, kind)
        if item is not None and item.has_signal():
            items.append(item)
    return items


def policy_strong_high_risk_gate(
    task: Task, calibration: Calibration, config: Config
) -> PolicyResult:
    """Narrow gate: trust the strong verifier except on high-risk accepts.

    Low/medium risk keeps the strong verifier's full coverage.  High risk must
    satisfy provenance-aware sufficiency before acceptance; otherwise the gate
    returns INDETERMINATE rather than accepting on correlated evidence.
    """
    strong = _first(task, "strong_judge")
    budget = config.budget[task.risk]
    if task.risk != "high":
        if strong is None or strong.cost > budget + 1e-9:
            return _result("INDETERMINATE", [], calibration.prior_subclaim)
        supported = _supports_required(strong, config)
        confidence, per = claim_confidence(
            [strong], calibration, config, blind=False, scope_aware=True
        )
        if supported is True:
            return _result("ACCEPT", [strong], confidence, per)
        if supported is False:
            return _result("REJECT", [strong], confidence, per)
        return _result("INDETERMINATE", [strong], confidence, per)

    items: List[EvidenceItem] = []
    cost = 0.0
    for item in _integrity_evidence(task):
        if cost + item.cost > budget + 1e-9:
            continue
        items.append(item)
        cost += item.cost
    confidence, per = claim_confidence(
        items, calibration, config, blind=False, scope_aware=True
    )
    return _result(decide(confidence, task.risk, config), items, confidence, per)


def _contradiction_subclaims(
    items: Sequence[EvidenceItem], calibration: Calibration, config: Config
) -> List[int]:
    disputed: List[int] = []
    for j in range(config.n_subclaims):
        groups: Dict[Tuple[str, ...], List[bool]] = {}
        for item in items:
            verdict = _verdict_for(item, j, True)
            if verdict is None:
                continue
            groups.setdefault(_cluster_key(item), []).append(verdict)
        cluster_verdicts = {_majority(verdicts) for verdicts in groups.values()}
        cluster_verdicts.discard(None)
        if True in cluster_verdicts and False in cluster_verdicts:
            disputed.append(j)
    return disputed


def policy_contradiction_driven(
    task: Task, calibration: Calibration, config: Config
) -> PolicyResult:
    """Acquire evidence only to resolve a specific disputed subclaim."""
    acquired: List[EvidenceItem] = []
    cost = 0.0
    budget = config.budget[task.risk]

    det = _first(task, "det_rule")
    cheap = _first(task, "cheap_judge")
    for item in (det, cheap):
        if item is not None and item.has_signal() and cost + item.cost <= budget + 1e-9:
            acquired.append(item)
            cost += item.cost

    candidates = [
        item for item in task.evidence
        if item.has_signal()
        and item.kind != "format_check"
        and item is not det
        and item is not cheap
    ]
    candidates.sort(key=lambda item: (item.cost, item.evidence_id))

    while True:
        disputed = _contradiction_subclaims(acquired, calibration, config)
        if not disputed:
            break
        chosen = next(
            (
                item for item in candidates
                if item not in acquired
                and any(item.covers(j) for j in disputed)
                and not _is_redundant(item, acquired)
                and cost + item.cost <= budget + 1e-9
            ),
            None,
        )
        if chosen is None:
            break
        acquired.append(chosen)
        cost += chosen.cost

    confidence, per = claim_confidence(
        acquired, calibration, config, blind=False, scope_aware=True
    )
    return _result(decide(confidence, task.risk, config), acquired, confidence, per)


def policy_oracle(task: Task, calibration: Calibration, config: Config) -> PolicyResult:
    """Diagnostic upper bound using ground truth. Never deployable."""
    decision = "ACCEPT" if task.truth else "REJECT"
    confidence = 1.0 if task.truth else 0.0
    return _result(decision, [], confidence)


POLICIES = {
    "no_verify": policy_no_verify,
    "single_det": policy_single_det,
    "single_cheap": policy_single_cheap,
    "single_strong": policy_single_strong,
    "majority_vote": policy_majority_vote,
    "fixed_cascade": policy_fixed_cascade,
    "naive_count": policy_naive_count,
    "blind_bayes": policy_blind_bayes,
    "provenance_aware": policy_provenance_aware,
    "blind_sequential": policy_blind_sequential,
    "provenance_sequential": policy_provenance_sequential,
    "provenance_sequential_strong_first": policy_provenance_sequential_strong_first,
    "strong_high_risk_gate": policy_strong_high_risk_gate,
    "contradiction_driven": policy_contradiction_driven,
    "oracle (diagnostic)": policy_oracle,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denominator
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denominator
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def _contradiction_flag(task: Task, calibration: Calibration, config: Config) -> bool:
    initial = [
        item for item in task.evidence
        if item.kind in ("det_rule", "cheap_judge") and item.has_signal()
    ]
    # Only the first cheap judge, not its duplicates.
    seen_cheap = False
    filtered = []
    for item in initial:
        if item.kind == "cheap_judge":
            if seen_cheap:
                continue
            seen_cheap = True
        filtered.append(item)
    return bool(_contradiction_subclaims(filtered, calibration, config))


def _unknown_provenance_acquired(
    outcome: PolicyResult, task: Task
) -> bool:
    by_id = {item.evidence_id: item for item in task.evidence}
    return any(
        by_id[eid].ancestry is None
        for eid in outcome.evidence_ids
        if eid in by_id
    )


def summarize(
    outcomes: Sequence[PolicyResult],
    tasks: Sequence[Task],
    calibration: Calibration,
    config: Config,
) -> Dict[str, object]:
    n = len(tasks)
    n_good = sum(1 for task in tasks if task.truth)
    n_bad = n - n_good
    accepts = sum(1 for o in outcomes if o.decision == "ACCEPT")
    rejects = sum(1 for o in outcomes if o.decision == "REJECT")
    indeterminate = n - accepts - rejects
    false_accepts = sum(
        1 for o, t in zip(outcomes, tasks) if o.decision == "ACCEPT" and not t.truth
    )
    false_rejects = sum(
        1 for o, t in zip(outcomes, tasks) if o.decision == "REJECT" and t.truth
    )
    correct = sum(
        1 for o, t in zip(outcomes, tasks)
        if (o.decision == "ACCEPT" and t.truth)
        or (o.decision == "REJECT" and not t.truth)
    )
    accepted_and_correct = sum(
        1 for o, t in zip(outcomes, tasks) if o.decision == "ACCEPT" and t.truth
    )
    total_cost = sum(o.cost for o in outcomes)
    total_acquisitions = sum(o.acquisitions for o in outcomes)
    risk_loss = 0.0
    brier = 0.0
    redundant = 0
    contradiction_n = 0
    contradiction_correct = 0
    contradiction_indeterminate = 0
    unknown_n = 0
    unknown_indeterminate = 0
    unknown_false_accepts = 0

    for outcome, task in zip(outcomes, tasks):
        if outcome.decision == "ACCEPT" and not task.truth:
            risk_loss += config.loss_fa[task.risk]
        elif outcome.decision == "REJECT" and task.truth:
            risk_loss += config.loss_fr[task.risk]
        elif outcome.decision == "INDETERMINATE":
            risk_loss += config.loss_indet[task.risk]
        brier += (outcome.confidence - (1.0 if task.truth else 0.0)) ** 2

        by_id = {item.evidence_id: item for item in task.evidence}
        seen_ancestry = set()
        for eid in outcome.evidence_ids:
            item = by_id.get(eid)
            if item is None:
                continue
            if item.ancestry is not None:
                if item.ancestry in seen_ancestry:
                    redundant += 1
                seen_ancestry.add(item.ancestry)

        if _contradiction_flag(task, calibration, config):
            contradiction_n += 1
            if (outcome.decision == "ACCEPT" and task.truth) or (
                outcome.decision == "REJECT" and not task.truth
            ):
                contradiction_correct += 1
            if outcome.decision == "INDETERMINATE":
                contradiction_indeterminate += 1

        if _unknown_provenance_acquired(outcome, task):
            unknown_n += 1
            if outcome.decision == "INDETERMINATE":
                unknown_indeterminate += 1
            if outcome.decision == "ACCEPT" and not task.truth:
                unknown_false_accepts += 1

    far = false_accepts / n_bad if n_bad else 0.0
    frr = false_rejects / n_good if n_good else 0.0
    far_interval = wilson_interval(false_accepts, n_bad)
    frr_interval = wilson_interval(false_rejects, n_good)

    return {
        "n": n,
        "n_good": n_good,
        "n_bad": n_bad,
        "accepts": accepts,
        "rejects": rejects,
        "indeterminate": indeterminate,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "far": round(far, 4),
        "far_wilson": far_interval,
        "frr": round(frr, 4),
        "frr_wilson": frr_interval,
        "success_rate": round(correct / n, 4) if n else 0.0,
        "accepted_and_correct_rate": round(accepted_and_correct / n, 4) if n else 0.0,
        "indeterminate_rate": round(indeterminate / n, 4) if n else 0.0,
        "cost_total": round(total_cost, 4),
        "cost_per_task": round(total_cost / n, 4) if n else 0.0,
        "cost_per_success": round(total_cost / correct, 4) if correct else None,
        "avg_acquisitions": round(total_acquisitions / n, 4) if n else 0.0,
        "redundancy_rate": round(redundant / total_acquisitions, 4) if total_acquisitions else 0.0,
        "risk_weighted_loss": round(risk_loss, 4),
        "brier": round(brier / n, 6) if n else 0.0,
        "contradiction_n": contradiction_n,
        "contradiction_correct_rate": round(contradiction_correct / contradiction_n, 4) if contradiction_n else None,
        "contradiction_indeterminate_rate": round(contradiction_indeterminate / contradiction_n, 4) if contradiction_n else None,
        "unknown_n": unknown_n,
        "unknown_indeterminate_rate": round(unknown_indeterminate / unknown_n, 4) if unknown_n else None,
        "unknown_far": round(unknown_false_accepts / unknown_n, 4) if unknown_n else None,
    }


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------


def run_seed(
    n_calibration: int,
    n_evaluation: int,
    seed: int,
    config: Config = DEFAULT_CONFIG,
    cal_config: Optional[Config] = None,
) -> Tuple[Calibration, List[Task], Dict[str, List[PolicyResult]]]:
    if cal_config is None:
        cal_config = config
    if cal_config.n_subclaims != config.n_subclaims:
        raise ValueError("calibration and evaluation must share n_subclaims")

    calibration_seed = stable_seed(seed, "cal")
    evaluation_seed = stable_seed(seed, "eval")
    calibration_tasks, _ = generate_tasks(n_calibration, 0, calibration_seed, cal_config)
    _, evaluation_tasks = generate_tasks(0, n_evaluation, evaluation_seed, config)
    calibration = calibrate(calibration_tasks, cal_config)

    outcomes: Dict[str, List[PolicyResult]] = {}
    for name, policy in POLICIES.items():
        outcomes[name] = [policy(task, calibration, config) for task in evaluation_tasks]
    return calibration, evaluation_tasks, outcomes


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def run_full(
    seeds: Sequence[int] = (42, 123, 456, 789, 1024),
    n_calibration: int = 200,
    n_evaluation: int = 500,
    config: Config = DEFAULT_CONFIG,
    cal_config: Optional[Config] = None,
) -> Dict[str, object]:
    per_seed: Dict[str, Dict[str, object]] = {}
    calibrations: Dict[str, object] = {}
    for seed in seeds:
        calibration, tasks, outcomes = run_seed(
            n_calibration, n_evaluation, seed, config, cal_config
        )
        calibrations[str(seed)] = asdict(calibration)
        per_seed[str(seed)] = {
            name: summarize(results, tasks, calibration, config)
            for name, results in outcomes.items()
        }

    summary: Dict[str, object] = {}
    for name in POLICIES:
        rows = [per_seed[str(seed)][name] for seed in seeds]
        total_fa = sum(row["false_accepts"] for row in rows)
        total_bad = sum(row["n_bad"] for row in rows)
        total_fr = sum(row["false_rejects"] for row in rows)
        total_good = sum(row["n_good"] for row in rows)
        summary[name] = {
            "mean_success_rate": _mean([row["success_rate"] for row in rows]),
            "min_success_rate": round(min(row["success_rate"] for row in rows), 4),
            "max_success_rate": round(max(row["success_rate"] for row in rows), 4),
            "mean_cost_per_success": _mean([row["cost_per_success"] for row in rows]),
            "mean_cost_per_task": _mean([row["cost_per_task"] for row in rows]),
            "mean_risk_weighted_loss": _mean([row["risk_weighted_loss"] for row in rows]),
            "mean_indeterminate_rate": _mean([row["indeterminate_rate"] for row in rows]),
            "mean_accepted_and_correct_rate": _mean([row["accepted_and_correct_rate"] for row in rows]),
            "mean_redundancy_rate": _mean([row["redundancy_rate"] for row in rows]),
            "mean_brier": _mean([row["brier"] for row in rows]),
            "mean_contradiction_correct_rate": _mean([row["contradiction_correct_rate"] for row in rows]),
            "mean_unknown_indeterminate_rate": _mean([row["unknown_indeterminate_rate"] for row in rows]),
            "mean_unknown_far": _mean([row["unknown_far"] for row in rows]),
            "pooled_far": round(total_fa / total_bad, 4) if total_bad else 0.0,
            "pooled_far_wilson": wilson_interval(total_fa, total_bad),
            "pooled_frr": round(total_fr / total_good, 4) if total_good else 0.0,
            "pooled_frr_wilson": wilson_interval(total_fr, total_good),
            "total_evaluations": len(seeds) * n_evaluation,
        }

    return {
        "seeds": list(seeds),
        "n_calibration": n_calibration,
        "n_evaluation": n_evaluation,
        "config": asdict(config),
        "calibration_config": asdict(cal_config if cal_config is not None else config),
        "calibrations": calibrations,
        "summary": summary,
        "per_seed": per_seed,
    }


# ---------------------------------------------------------------------------
# Adversarial and distribution-shift conditions
# ---------------------------------------------------------------------------


def conditions() -> Dict[str, Tuple[Config, Config]]:
    """(evaluation config, calibration config) pairs.

    Calibration is always clean unless stated; evaluation applies the attack or
    shift.  This measures what happens when the policy's priors are stale or the
    provenance metadata is hostile.
    """
    base = DEFAULT_CONFIG
    return {
        "baseline": (base, base),
        "duplicate_attack": (replace(base, dup_copies=3), base),
        "shared_model": (replace(base, share_p=1.0, family_good_prob=0.5), base),
        "unknown_provenance": (replace(base, unk_rate=1.0), base),
        "false_provenance": (replace(base, false_prov_rate=1.0), base),
        "scope_mismatch": (replace(
            base,
            det_applicable_rate=0.0,
            ext_available_rate=0.0,
            share_p=1.0,
            family_good_prob=0.5,
        ), base),
        "distribution_shift": (replace(
            base,
            family_good_prob=0.4,
            ext_accuracy=0.6,
            unk_rate=0.6,
        ), base),
        "cost_exhaustion": (replace(
            base,
            budget={"low": 0.10, "med": 0.10, "high": 0.10},
        ), base),
        "correlated_failure": (replace(
            base,
            share_p=1.0,
            family_good_prob=0.2,
        ), base),
        "stale_evidence": (replace(base, stale_rate=0.5), base),
    }


def run_all(
    seeds: Sequence[int] = (42, 123, 456, 789, 1024),
    n_calibration: int = 200,
    n_evaluation: int = 500,
) -> Dict[str, object]:
    baseline = run_full(seeds, n_calibration, n_evaluation)
    condition_results: Dict[str, object] = {}
    for name, (eval_config, cal_config) in conditions().items():
        condition_results[name] = run_full(
            seeds=(42, 123, 456),
            n_calibration=150,
            n_evaluation=300,
            config=eval_config,
            cal_config=cal_config,
        )
    return {
        "meta": {
            "generated_by": "experiments/benchmark/evidence_integrity.py",
            "baseline_seeds": list(seeds),
            "baseline_n_calibration": n_calibration,
            "baseline_n_evaluation": n_evaluation,
            "condition_seeds": [42, 123, 456],
            "condition_n_calibration": 150,
            "condition_n_evaluation": 300,
        },
        "baseline": baseline,
        "conditions": condition_results,
    }


def main() -> Dict[str, object]:
    results = run_all()
    output_dir = Path("experiments/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evidence_integrity_results.json"
    output_path.write_text(
        json.dumps(results, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(results["baseline"]["summary"], indent=2, sort_keys=True))
    return results


if __name__ == "__main__":
    main()

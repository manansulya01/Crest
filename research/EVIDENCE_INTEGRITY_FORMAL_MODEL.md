# Evidence Integrity — Formal Model

Status: working specification for Cycle 3 experiments. Assumptions are explicit;
no result from simulation is claimed as a live property.

## 1. Objects

Let `C` be the claim under evaluation (e.g., "transaction X was authorized").

Each evidence object `e` carries:

- `a(e)` — **ancestry**: set of original source families it derives from
  (`{s1}`, `{s2}`, …, or `UNKNOWN`).
- `t(e)` — **claim scope**: the set of sub-claims it bears on.
- `ρ(e)` — **reliability**: P(this evidence is correct | its source family is
  correct), estimated/assumed per verifier class (deterministic rule, cheap
  judge, strong judge, external source).
- `fresh(e)` — freshness/staleness flag.
- `origin_meta(e)` ∈ {known, missing, false} — provenance metadata status.

An **original source family** `s ∈ S` has hidden quality `Q_s ∈ {good, bad}` with
prior `P(good) = p_s`. All evidence derived from `s` is correct iff `Q_s = good`
(up to independent per-item noise `η_s`, typically `η_s ≈ 0.05`).

## 2. Independence clusters

Define **clusters**: `cluster(e) = {s : s ∈ a(e)}`. Two evidence items are
*independent* iff their ancestry sets are disjoint AND both are known.
Unknown ancestry is treated as its own cluster and is *not* independent of
anything else (conservative rule).

## 3. Agreement without independence is not confirmation

If two evidence items agree, and both derive from one bad source, their
agreement proves nothing about the claim. Hence:

> **Rule E1 (common-cause discount).** For evidence cluster `K`, the group
> contributes at most one independent unit of support. For a claim validated by
> `m` clusters with per-source accuracy `a`,
>
>   P(at least one correct independent source | Q) = 1 − (1 − a)^m
>
> with `a` drawn from source-quality priors, **not** from the number of items.

## 4. Claim-level assurance and decision loss

The claim is partitioned into sub-claims `c = (c_1, …, c_n)` with required
assurance `s_i(risk)`. Evidence may cover only a subset of `c_i`.

Decision outcomes: `ACCEPT`, `REJECT`, `REQUEST_MORE_EVIDENCE`, `ESCALATE`,
`INDETERMINATE`.

Loss matrix (parameterised, configurable):
   L(ACCEPT, bad)   = W_accept(risk)        — false acceptance
   L(REJECT, good)  = W_reject(risk)        — false rejection
   L(INDETERM.)     = W_indet(risk, cost)   — cost of unresolved evidence

Risk-weighted expected loss: `EL(π) = Σ_e P(e | policy π, evidence) · L(π(e), e)`.

## 5. Posterior update

Given agreement evidence `E`,

   P(H | E) ∝ P(H) ∏_clusters P(E_cluster | H, Q)

where within a cluster the joint likelihood depends on `Q_s` (shared), not on
independent items. This yields the fundamental asymptote: `m` agreeing items
from ONE family raise confidence no more than one item from that family.

## 6. Unknown dependency

If `a(e) = UNKNOWN` for any decisive item, the aggregation must not assign it
independence credit. Conservative rule:

> **Rule E2 (unknown provenance cap).** Confidence contributed by unknown-provenance
> evidence is capped at `cap_unk` (e.g., 0.5 × independent evidence), and the
> decision cannot exceed `ACCEPT` without at least one known-ancestry
> independent support, unless the risk class is `low`.

## 7. Scope mismatch

Evidence that does not entail `c_i` contributes 0 to `c_i` assurance. Agreement
on an out-of-scope sub-claim is irrelevant evidence for the decision.

> **Rule E3 (scope gating).** Aggregate assurance per sub-claim, not globally.
> A fully supported claim except for one missing sub-claim is *insufficient*.

## 8. Stopping and budget

Evidence acquisition is sequential with cost. Stop when either:
1. Expected loss of deciding now < expected loss of gathering more evidence, or
2. Budget exhausted → `INDETERMINATE` (never fabricate certainty).

## 9. Worked example

Claim: "Invoice #4521 is valid and must be paid."

Evidence:
- E1: LLM judge A says valid — ancestry {model-family-1}, known, scope {total, vendor}.
- E2: LLM judge B says valid — ancestry {model-family-1}, known, scope {total, vendor} ← same family.
- E3: Deterministic checksum of line items — ancestry {none — deterministic}, known, scope {line-items}.
- E4: Vendor registry lookup — ancestry {external-registry}, unknown-freshness, scope {vendor}.

Naive vote: 3-1 valid → high confidence.
Provenance-aware: clusters = {model-family-1 (E1,E2 → one unit), rule (E3),
registry (E4, unknown → discounted)} → independent support units = 2 (rule +
registry-discounted) + the model family counted once. Vendor scope has registry
(discounted) + model agreement — still below high-risk bar → decision:
REQUEST_MORE_EVIDENCE or ACCEPT only if risk=low.

## 10. Assumptions and limitations

- Source qualities are not directly observable; priors come from history or are
  estimated with explicit uncertainty — **not** from the models' own outputs.
- The simulator is a controlled world, not a claim about real traffic.
- Correlation structure between *unknown* sources cannot be estimated; the
  mechanism must prefer INDETERMINATE over confident error.
- Semantic verifiers remain fallible in correlated ways; the mechanism limits
  damage but cannot eliminate it.
- All probabilities shown are illustrative; the experiment measures behaviour,
  not metaphysical truth.

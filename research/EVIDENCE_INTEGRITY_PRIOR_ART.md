# Evidence Integrity — Prior-Art Audit

Research date: 2026-11-04. Sources verified against current documentation and
publications. Verified facts vs. hypotheses are flagged.

## 1. Provenance and lineage (database science)

- **Provenance semirings** (Green, Karvounarakis, Tannen, PODS 2007; extended
  2017) — formal semantics for why-provenance using polynomial semirings.
  Verified fact: identical derivations can be identified by shared atomic
  facts. Verified limitation: designed for database queries, not for runtime
  model-execution decisions.
- **Glavic, "Data provenance"** (Foundations and Trends in Databases,
  2010/2021) — systematic survey of why/where provenance.
- **ULDBs** (Benjelloun et al., VLDB 2006) — uncertainty + lineage in
  probabilistic databases.
- **Why/where provenance** (Buneman, Khanna, Tan, ICDT 2001).

**Overlap with CREST:** dependency tracking and shared-ancestry detection is a
solved database problem. **Difference:** provenance semirings do not decide
whether evidence is *sufficient for a claim*, do not weigh semantic
reliability, and do not resolve contradictory evidence. They track *lineage*,
not *decision value*.

## 2. Assurance cases and safety argumentation

- **Goal Structuring Notation (GSN)** (Kelly & Weaver, 2004) — structured
  claim-argument-evidence trees with context and assumptions.
- **GSN Community Standard v3** (Safety-Critical Systems Club, 2021).
- Recent LLM-assisted assurance-case work: Odu et al. (JSS 2025), Yu et al.
  (JSS 2026), CERN LHC machine-protection case (Millet et al., NASA TM
  2025-01849). Trusta (Chen, Deng, Du, 2023) — formal-methods checking of
  AI-generated assurance arguments.

**Overlap:** explicit claims, evidence, assumptions, rebuttals; assurance
cases embody the idea "evidence must support a *specific* claim."
**Difference:** GSN is human-authored and static; it has no runtime execution
gate, no cost-aware evidence acquisition, and no quantitative dependency-aware
aggregation. It is a *documentation and argumentation* technology, not a
decision-time control.

## 3. Bayesian networks and common-cause failure

- Bayesian network theory for common cause failure (Li et al.; Sun et al.,
  Reliability Engineering & System Safety 2021; Nature Scientific Reports 2026).
- Berkeley CS188 lectures on common cause vs common effect (active paths;
  "knowing X tells about Y").
- Byzantine fault papers apply quorum thinking to multi-agent AI (Cowling et
  al. OSDI 2006; AAAI 2026 "Rethinking the Reliability of Multi-Agent
  Systems"; "Epistemic Byzantine Fault Tolerance", 2026; arXiv 2607.16109).

**Overlap:** shared-ancestry (common cause) is a known physical-fault mode;
CREST's "shared source" failure is the same phenomenon in evidence space.
**Difference:** BFT replication assumes independent process replicas and a
majority-agreement rule with identical deterministic responses; AI verifiers
are stochastic, correlated, and non-identical — majority vote logic does not
transfer directly. Quorum size ≥3 still cannot detect a shared-cause error.

## 4. LLM-as-a-judge and evaluator reliability

Verified findings:
- LLM-as-judge suffers positional, verbosity, self-enhancement biases
  (Chiang & Lee 2023; Zheng et al. 2023; Liu et al. 2024).
- "Causal Judge Evaluation" (Landesberg et al. 2025) and JudgeBench (Tan et
  al. 2025) — judge agreement with oracle labels is not reliable on hard
  tasks; mutual biases distort evaluation (Santilli et al. 2025).
- A 2025 survey (Elsevier) documents known failure modes and mitigations.
- Community reports ("LLM-as-judge is not a verification layer, it is a second
  failure mode") — repeated practitioner finding.

**Implication:** agreement between two AI judges is *not* independent
evidence when both were produced by related models. Any aggregation that
counts agreements linearly will over-count correlated evidence.

## 5. Observability / tracing platforms

- **Langfuse** (open source, MIT; acquired by ClickHouse 2026) — traces,
  scores, observation trees. **Phoenix** (Elastic License), **Helicone**
  (Apache-2.0, in maintenance posture after Mintlify acquisition 2026),
  **Arize**, **LangSmith**, **OpenTelemetry SemConv** (gen_ai.* conventions).
- **ExecWeave** (arXiv 2610.21146, 2026) — cross-layer execution provenance
  for agents; surveys existing agent observability.

**Verified fact about the ecosystem:** none of these systems estimates
whether *agreement among verifiers is independent evidence*. They record
*that* checks occurred and their raw outputs; they do not model shared
ancestry between verifiers, do not apply common-cause discounting, and do not
block or degrade decisions based on provenance uncertainty. ExecWeave surveys
agent traces but again focuses on observability, not on sufficiency decisions.

## 6. Formal methods and trusted computing base

- Proof-carrying code (Necula & Lee 1996), runtime verification, Design by
  Contract (Meyer 1992), model checking, Hoare logic.
- Deterministic checks (checksums, type systems, schema validators) are
  categorically stronger than model judgments — a distinction CREST's
  evidence model must preserve.

**Overlap:** deterministic proof > probabilistic support is uncontroversial.
**Difference:** formal methods verify *programs*, not *open-ended language
claims*; their scope is limited but their strength inside it is absolute.

## 7. Court of prior art summary

| Candidate CREST idea | Closest prior art | Actual difference |
|---|---|---|
| Evidence provenance graph | DB provenance semirings; ExecWeave traces | Runtime *decision-time* gate that reasons about provenance to *decide*, not merely record |
| Dependency-aware confidence | Common-cause Bayesian nets; quorum BFT | Domain is AI verifiers on natural-language claims; unknown-dependency handling must be conservative |
| Claim-level sufficiency | GSN assurance cases | Quantitative, cost-aware, runtime, with automated acquisition and invalidation |
| Contradiction-driven acquisition | Fault-tree / FMEA analyses | Automated, budget-bounded evidence acquisition targeting the *specific disputed claim* |
| Decision integrity gate | Admission policy (CREST v0.5), authorization engines | Combines provenance, uncertainty, and risk-class thresholds into one structured decision |

## 8. Honest novelty assessment

- The ingredients (provenance, common-cause discounting, GSN claims, SPRT,
  admission gates) are all published.
- What I could not find in any single published system: a **runtime execution
  gate that discounts verifier agreement by provenance-derived independence,
  refuses to amplify confidence under unknown dependency, and couples the
  resulting bound to a risk-weighted execution decision**. This is an
  integration of known parts, not a new fundamental mechanism.
- Classification: **new integration** leaning toward **new experimentally
  demonstrated capability** only if the benchmark shows the combination beats
  strong baselines under adversarial conditions.

## 9. What would falsify the idea

- If dependency-aware discounting never improves error bounds vs naive voting
  on a realistic evidence distribution, the mechanism adds complexity without
  value.
- If unknown provenance is common enough that the conservative rule blocks
  every real decision (all INDETERMINATE), the mechanism is unusable.
- If verifiers are already independent in practice, provenance tracking is
  overhead with no payoff.

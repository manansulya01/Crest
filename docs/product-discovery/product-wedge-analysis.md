# Product Wedge Analysis

## Scoring criteria (weights)

| Criterion | Weight | Rationale |
|---|---|---|
| Problem severity | 25% | How much pain does the problem cause? |
| Competitive gap | 25% | How poorly do existing tools solve it? |
| Technical defensibility | 20% | Can CREST demonstrate a measurable advantage? |
| Adoption friction | 15% | How easy is it to integrate? |
| Time to first value | 10% | How quickly can a user see benefit? |
| Willingness-to-pay hypothesis | 5% | Is there a plausible revenue model? |

Scores: 1-5 (1=weak, 5=strong). Weighted total out of 5.

## Direction 1: Inference Budget Firewall

**Problem:** Developers need guarantees that AI workflows cannot exceed authorized spending.

| Criterion | Score | Reasoning |
|---|---|---|
| Problem severity | 4 | Cost overruns are real and painful, but existing tools (LiteLLM, Cloudflare) already provide hard budget enforcement. The pain is more about configuration than capability. |
| Competitive gap | 2 | LiteLLM has the deepest open-source budget hierarchy (per-key/user/team, multi-window, hard enforcement). Cloudflare added dollar limits. Portkey has budget limits (Enterprise). The gap is narrow: pre-inference reservation vs. post-hoc tracking. |
| Technical defensibility | 3 | CREST's pre-inference reservation (never refunded, fail-closed) is a genuine differentiator vs. post-hoc tracking. But it's a single-host SQLite implementation, not distributed. |
| Adoption friction | 4 | Library-only, no CLI, no deployment. High friction vs. LiteLLM (Docker) or Cloudflare (managed). |
| Time to first value | 3 | Requires integration into existing code. No quick win. |
| Willingness-to-pay | 2 | Budget enforcement is a feature, not a product. Users expect it in gateways. |
| **Weighted total** | **3.15** | |

**Reasons it could fail:** LiteLLM already solves this well in open source. Budget enforcement is commoditizing (Cloudflare added it in 2026). CREST's single-host SQLite limitation makes it unsuitable for production multi-tenant use. The gap (pre-inference vs. post-hoc) may not matter enough to users to justify a new tool.

## Direction 2: Auditable Inference Ledger

**Problem:** Developers need trustworthy records of what each AI task actually consumed and what it cost.

| Criterion | Score | Reasoning |
|---|---|---|
| Problem severity | 3 | Cost attribution is painful but most teams handle it with existing observability (Langfuse, Helicone, LiteLLM logs). The pain is more about reconciliation than recording. |
| Competitive gap | 2 | Langfuse tracks cost per trace/user/session/model. LiteLLM tracks per-key/user/team. Helicone per-request. All have cost tracking. CREST's differentiator is unknown-cost honesty (cost_known flag) and task-level attribution, but this is a feature gap, not a product gap. |
| Technical defensibility | 3 | CREST's cost_known flag and task-level ledger are genuinely different from provider-level tracking. But no tool currently reconciles provider billing with application estimates — this is a real gap. |
| Adoption friction | 4 | Library-only, requires code changes. High friction. |
| Time to first value | 3 | Requires integration. |
| Willingness-to-pay | 2 | Observability is crowded (Langfuse, Helicone, Datadog). Hard to charge for another observability tool. |
| **Weighted total** | **2.85** | |

**Reasons it could fail:** The observability space is saturated. CREST's ledger is a feature, not a product. Provider billing reconciliation is a real gap but requires provider API access and is complex. No evidence that users would pay for this specifically.

## Direction 3: Verified Execution Runtime

**Problem:** Developers need execution guarantees beyond receiving a model response — invalid outputs must not silently become successful task results.

| Criterion | Score | Reasoning |
|---|---|---|
| Problem severity | 3 | Invalid structured output is a real problem, but developers handle it with retry logic and schema validation (Pydantic, Zod, JSON Schema). The pain is more about reliability than a missing capability. |
| Competitive gap | 3 | TensorZero had structured inference with schema enforcement but is archived. Portkey has guardrails (Enterprise). No open-source tool has fail-closed execution where invalid output cannot be marked successful with auditable evidence. This is a real gap. |
| Technical defensibility | 4 | CREST's fail-closed execution (invalid output → denied, with audit trail) is genuinely different from existing tools. The runtime enforces that invalid outputs never become successful results. This is a defensible technical capability. |
| Adoption friction | 4 | Library-only. But the verification logic is simple and could be integrated into existing workflows. |
| Time to first value | 3 | Requires integration. |
| Willingness-to-pay | 3 | Reliability is valuable. Teams that need auditable verification (finance, healthcare, legal) might pay. But the market is unproven. |
| **Weighted total** | **3.35** | |

**Reasons it could fail:** Schema validation is a solved problem (Pydantic, Zod, JSON Schema). CREST's "fail-closed" is a nice property but may not be valuable enough to justify a new tool. The market for "verified execution" is unproven. Existing orchestration frameworks (LangGraph, CrewAI) are adding verification features.

## Direction 4: Combined Control Plane

**Problem:** A coherent system combining budget enforcement, accounting, and verified execution.

| Criterion | Score | Reasoning |
|---|---|---|
| Problem severity | 4 | The combination is valuable in theory. |
| Competitive gap | 2 | LiteLLM + Langfuse together cover most of this. Portkey covers gateway + guardrails. The combination is not a gap — it's a bundle. |
| Technical defensibility | 3 | CREST has all three pieces, but none is individually best-in-class. The combination is the value, but it's hard to defend against "just use LiteLLM + Langfuse." |
| Adoption friction | 5 | Very high. Requires replacing or augmenting existing infrastructure. |
| Time to first value | 2 | Long. |
| Willingness-to-pay | 2 | Hard to sell a bundle when components are available separately. |
| **Weighted total** | **2.95** | |

**Reasons it could fail:** Too broad. No single compelling reason to adopt. High friction. Competitors already bundle (Portkey = gateway + guardrails + observability). CREST would be competing against better-funded, more mature products.

## Recommendation

**Direction 3 (Verified Execution Runtime) scores highest (3.35/5).**

The narrowest valuable problem CREST could solve is: **ensuring that invalid AI outputs cannot silently become successful task results, with an auditable evidence trail.**

This is the only direction where:
1. A real competitive gap exists (no open-source tool has fail-closed execution with auditable evidence).
2. CREST has a genuinely different technical capability (not just a different implementation of the same feature).
3. The gap is not being rapidly closed by better-funded competitors (TensorZero was the closest, and it shut down).

However, the willingness-to-pay is unproven, and the market for "verified execution" is unclear. The recommendation is to NARROW further: test whether developers need fail-closed execution as a standalone capability, and whether CREST's implementation is better than "just add Pydantic validation."

**This is a NARROW recommendation, not a CONTINUE.**

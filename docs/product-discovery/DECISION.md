# Product Discovery Decision Report

## 1. Is there a real developer problem?

**Yes, but it is partially solved.**

Developers operating production LLM workloads face:
- Cost overruns from runaway retries, agent loops, and unexpected traffic.
- Invalid structured outputs that silently propagate downstream.
- Lack of per-task cost attribution and audit trails.
- Provider billing discrepancies that are hard to reconcile.

These problems are real (evidenced by the existence of LiteLLM budgets, Portkey
guardrails, Helicone alerts, and Langfuse cost tracking). However, the severity
varies: cost overruns are the most painful (direct financial impact), while
invalid outputs are usually caught by application-level validation.

**Confidence: Medium** (problems are real but severity is inferred from
competitive landscape, not from direct user interviews).

## 2. Who experiences it?

- AI application developers (building LLM-powered features).
- Platform/infrastructure engineers (operating LLM workloads).
- Engineering leads (managing AI budgets).

Most acutely: teams with production LLM workloads and meaningful inference spend
(>$1K/month), especially those with multi-tenant or multi-workflow systems.

## 3. How severe and frequent is it?

- Cost overruns: Frequent (any team running agents or batch processing). Severity:
  High (direct financial impact, can be thousands of dollars).
- Invalid outputs: Frequent (LLMs are unreliable). Severity: Medium (usually
  caught by application logic, but silent failures cause downstream bugs).
- Audit/reconciliation: Infrequent but severe (compliance, financial reporting).

**Confidence: Medium** (inferred from competitive landscape and tool feature sets,
not from direct user interviews).

## 4. How do they solve it today?

- **Budget enforcement:** LiteLLM (per-key/user/team budgets, hard enforcement).
  Cloudflare AI Gateway (dollar limits, open beta). Custom middleware.
- **Cost tracking:** Helicone, Langfuse, LiteLLM logs, provider dashboards.
- **Output validation:** Pydantic, Zod, JSON Schema, custom retry logic.
- **Audit trails:** Langfuse traces, provider logs, custom logging.

Most teams use a combination of 2-3 tools (gateway + observability + application
validation). No single tool covers all three.

## 5. What do existing tools already solve?

| Capability | Best existing solution | Maturity |
|---|---|---|
| Budget enforcement (hard) | LiteLLM (open source, per-key/user/team) | Mature |
| Cost tracking (per-request) | Helicone, Langfuse, LiteLLM | Mature |
| Cost attribution (per-tenant) | LiteLLM (teams), Langfuse (sessions) | Mature |
| Output validation | Pydantic, Zod, JSON Schema | Mature |
| Retry on invalid output | Application-level (custom) | Mature |
| Audit trails | Langfuse, provider logs | Mature |
| Fail-closed execution | None (no open-source tool) | Gap |
| Unknown-cost honesty | None (all treat provider usage as ground truth) | Gap |
| Pre-inference budget reservation | None (all post-hoc) | Gap |

## 6. What meaningful gap remains?

Three gaps exist:

1. **Pre-inference budget reservation** (not post-hoc tracking): No tool reserves
   budget before execution and fails closed if the reservation cannot be made.
   LiteLLM tracks spend after the fact; Cloudflare limits are post-hoc.
   CREST's pre-inference reservation is genuinely different.

2. **Unknown-cost honesty**: No tool explicitly tracks when cost cannot be
   determined (unsupported model, missing usage). All treat provider-reported
   usage as ground truth, even when it's $0 for unsupported models.
   CREST's `cost_known` flag is genuinely different.

3. **Fail-closed execution with audit trail**: No open-source tool enforces that
   invalid outputs cannot be marked as successful, with an auditable evidence
   trail for every attempt. TensorZero had structured inference but is archived.
   CREST's InferenceRuntime does this by construction.

These gaps are real but narrow. They are features, not products. The question is
whether they are valuable enough to justify a standalone tool.

## 7. Why is CREST positioned to solve it?

CREST has a working implementation of all three gaps:
- Pre-inference budget reservation (SQLite-backed, atomic at single-host level).
- Unknown-cost honesty (`cost_known` flag, `usage_reported` on responses).
- Fail-closed execution (invalid output → denied, with audit trail and digest).

However, CREST is a Python library with no CLI, no deployment, no multi-tenancy,
no provider abstraction beyond OpenAI-compatible, and no enterprise features.
It is a research prototype, not a product.

## 8. What is the smallest credible product?

An **auditable inference control plane** — a lightweight library or service that:
1. Wraps LLM calls with budget enforcement (pre-inference reservation).
2. Records provider-reported usage honestly (with `cost_known` flag).
3. Fail-closes on invalid outputs (schema validation → denied, not successful).
4. Produces an auditable evidence trail (request_id, model, usage, attempts, status, digest).
5. Exports usage records for reconciliation.

This is NOT a gateway (no provider abstraction, no routing, no caching). It is a
control layer that sits between the application and the LLM call, enforcing
constraints and recording evidence.

Target user: developers building LLM-powered applications who need cost control
and auditability but don't want to adopt a full gateway.

## 9. What evidence is missing?

1. **User validation**: No customer interviews, no user research, no evidence that
   developers would adopt this over LiteLLM + Pydantic.
2. **Live verification**: The strong model is unavailable. No live comparative
   experiment on the verified execution capability.
3. **Reconciliation evidence**: No comparison of provider billing vs. application-level
   estimates to demonstrate the value of unknown-cost honesty.
4. **Adoption evidence**: No evidence that developers would integrate a new library
   rather than adding Pydantic validation to their existing code.
5. **Willingness to pay**: No evidence that anyone would pay for this.

## 10. What would invalidate the recommendation?

- If developers say "I just use Pydantic + LiteLLM and it's fine" → STOP.
- If the cost of integration exceeds the value of the audit trail → STOP.
- If provider billing reconciliation shows negligible discrepancy → NARROW (drop
  unknown-cost honesty as a differentiator).
- If no one needs fail-closed execution (they're fine with retry-and-hope) → STOP.

---

## Decision: NARROW

CREST should narrow to **verified execution with auditable evidence trails** as
its single most defensible capability.

**Rationale:**
1. Budget enforcement is already solved well by LiteLLM (open source) and
   Cloudflare (managed). CREST's pre-inference reservation is a genuine
   differentiator but the gap is narrow.
2. Usage accounting is crowded (Langfuse, Helicone, LiteLLM). CREST's unknown-cost
   honesty is unique but unproven valuable.
3. Verified execution with fail-closed semantics and audit trails is the only
   capability where CREST has a genuine, unaddressed gap (TensorZero was the
   closest, and it shut down). No open-source tool does this.

**Confidence: Medium** (technical capability is demonstrated; product value is
inferred from competitive gap, not from user evidence).

**Next action:** Conduct 5-10 customer interviews using the interview guide
(docs/product-discovery/customer-interview-guide.md) to validate whether
developers need fail-closed execution with audit trails, and whether they would
adopt a library for it. If interviews confirm demand → build the smallest
product slice. If not → STOP.

# Competitive Landscape — LLM Inference Gateways and Control Planes

Research date: November 2026. Sources: official documentation, pricing pages, and
credible technical comparisons. Marketing claims treated as unverified.

## Competitor comparison matrix

| Capability | LiteLLM | Portkey | Helicone | Langfuse | TensorZero | Cloudflare AI Gateway | CREST |
|---|---|---|---|---|---|---|---|
| **Budget enforcement** | Hard (per-key/user/team, multi-window) | Dollar+token cap (Enterprise) | Alerts only | No (observe only) | Archived (Jun 2026) | Dollar limits (open beta) | Pre-inference reservation (single-host) |
| **Usage accounting** | Per-key/user/team spend tracking | Per-request cost tracking | Per-request cost tracking | Per-trace/user/session/model | N/A (archived) | Request logging | Per-task ledger (SQLite) |
| **Cost attribution depth** | Key/user/team/tag | Provider integration | Per-request | Per-trace/model/user | N/A | Basic | Per-task with model identity |
| **Unknown cost handling** | Tracks $0 for unsupported models | Shows $0.00, no budget apply | Alerts only | Tracks cost per trace | N/A | Basic | Explicit `cost_known` flag, fail-closed |
| **Retry handling** | Automatic retries | Automatic retries + circuit breakers | Basic | N/A (observe) | N/A | Basic | Bounded retries (transient classification) |
| **Provider abstraction** | 100+ providers | 250+ providers | Proxy to providers | N/A (observe) | N/A (archived) | Managed providers | OpenAI-compatible only |
| **Structured output validation** | No | Guardrails (Enterprise) | No | No | Schema enforcement (archived) | No | Response validation (schema, tokens, finish reason) |
| **Policy enforcement** | Rate limits, budgets | Guardrails, budgets (Enterprise) | No | No | GitOps-based (archived) | Rate limits | Model allowlist, token limits, budget caps |
| **Execution verification** | No | Guardrails (Enterprise) | No | No | Inference-level feedback (archived) | No | Fail-closed: invalid output → denied |
| **Audit records** | Request logs (Enterprise: audit logs) | Audit trails (Enterprise) | Request logs | Trace logs | N/A (archived) | Request logs | SQLite ledger with digests |
| **Multi-tenancy** | Teams, users, keys | Virtual keys | Basic | Projects | N/A (archived) | Basic | Single-tenant (no hierarchy) |
| **Enterprise controls** | SSO, RBAC (Enterprise) | SSO, RBAC (Enterprise) | SOC 2, HIPAA (Team) | SSO (Enterprise) | N/A (archived) | Enterprise tier | None |
| **Deployment model** | Self-hosted (Docker) + cloud | Managed + on-prem | Managed + self-host | Self-hosted + cloud | Self-hosted (archived) | Managed (Cloudflare) | Library (Python) |
| **Pricing** | Open source (MIT) + Enterprise quote | Free tier + Enterprise ($2K-10K+/mo) | Free tier + Pro ($79/mo) + Team ($799/mo) | Free tier + Core ($29/mo) + Pro ($199/mo) | Archived | Pay-as-you-go | Open source |
| **Adoption friction** | Medium (requires Postgres/Redis) | Low (managed) / Medium (self-host) | Low | Low (self-host) / Medium | N/A (archived) | Low (managed) | High (library, no CLI, no deployment) |
| **Open source** | Yes (MIT) | Gateway open (Apache 2.0, Mar 2026) | Yes (Apache 2.0) | Yes (MIT) | Yes (archived) | No (managed) | Yes |

## Key findings

### Budget enforcement landscape
- **LiteLLM** has the deepest open-source budget hierarchy (per-key, per-user, per-team,
  multi-window, hard enforcement). Requires PostgreSQL + Redis. Enterprise features
  (SSO, RBAC, audit logs) behind paywall.
- **Cloudflare AI Gateway** added dollar spend limits (June 2026, open beta). Managed,
  low friction, but basic.
- **Portkey** budget limits are Enterprise-only. Cannot edit once set (must duplicate
  provider). Only counts requests made after limit is set.
- **Helicone** has alerts only (no hard enforcement). In maintenance mode (Mintlify
  acquisition, March 2026).
- **No open-source tool** combines pre-inference budget reservation (not post-hoc
  tracking) with honest unknown-cost handling and fail-closed execution.

### Usage accounting landscape
- **LiteLLM** tracks spend per key/user/team/tag. Good for attribution.
- **Langfuse** tracks cost per trace/user/session/model. Deep observability.
- **Portkey** tracks per-request cost. Shows $0 for unsupported models.
- **Helicone** per-request cost tracking. Simplest setup.
- **Gap:** No tool reconciles provider-reported usage with application-level
  estimates or flags discrepancies. All treat provider-reported usage as ground truth.

### Verified execution landscape
- **TensorZero** had structured inference with schema enforcement and GitOps-based
  operations — but is **archived** (June 2026). This is the closest to CREST's
  verification approach, and it shut down.
- **Portkey** has guardrails (Enterprise) — PII redaction, jailbreak detection.
- **No open-source tool** has fail-closed execution where invalid output cannot be
  marked as successful, with auditable evidence trails.

### Market consolidation (2026)
- Portkey acquired by Palo Alto Networks (May 2026).
- Helicone acquired by Mintlify (March 2026, maintenance mode).
- TensorZero archived (June 2026, returned capital).
- OpenRouter raised $113M Series B (May 2026).

The AI gateway space is consolidating rapidly. Smaller players are being acquired
or shutting down. The survivors (LiteLLM, Cloudflare, Portkey/Palo Alto) are
adding budget and guardrail features.

## Sources

- LiteLLM docs: https://docs.litellm.ai/docs/proxy/users, https://docs.litellm.ai/docs/proxy/team_budgets
- Portkey docs: https://docs.portkey.ai/docs/product/ai-gateway/virtual-keys/budget-limits
- Helicone docs: https://docs.helicone.ai/guides/cookbooks/cost-tracking
- Langfuse docs: https://langfuse.com/docs/observability/features/token-and-cost-tracking
- TensorZero: https://github.com/tensorzero/tensorzero (archived June 2026)
- Cloudflare AI Gateway: https://developers.cloudflare.com/ai-gateway/
- finops.qa comparison: https://finops.qa/blog/ai-gateway-cost-control-comparison-2026
- opper.ai gateway roundup: https://opper.ai/blog/best-llm-gateways
- lunar.dev gateway comparison: https://www.lunar.dev/post/top-5-ai-gateways-in-2026
- cloudzero.com gateway comparison: https://www.cloudzero.com/blog/llm-gateways
- compresr.ai spend dashboard comparison: https://compresr.ai/blog/ai-spend-dashboard-tools-track-attribute-cut-llm-costs
- amnic.com cost tracking tools: https://amnic.com/blogs/ai-cost-tracking-tools
- getmaxim.ai LLM gateways: https://www.getmaxim.ai/articles/top-5-llm-gateways-in-2025-the-definitive-guide-for-production-ai-applications
- truefoundry.com gateway comparison: https://www.truefoundry.com/blog/best-ai-gateways-for-llm-inference-optimization
- truefoundry.com LiteLLM pricing: https://www.truefoundry.com/blog/litellm-pricing-guide
- truefoundry.com Portkey pricing: https://www.truefoundry.com/blog/portkey-pricing-guide
- truefoundry.com Helicone pricing: https://www.truefoundry.com/blog/helicone-pricing
- activepieces.com LiteLLM enterprise: https://www.activepieces.com/blog/is-litellm-enterprise-pricing-worth-the-monthly-bill
- aimagicx.com AI agent spending guardrails: https://www.aimagicx.com/blog/ai-agent-spending-guardrails-budget-caps-2026
- requesty.ai LLM spend limits: https://www.requesty.ai/blog/llm-spend-limits-per-api-key-and-customer
- getmaxim.ai cost tracking tools: https://www.getmaxim.ai/articles/best-llm-cost-tracking-tools-in-2026
- laminar.sh LLM observability pricing: https://laminar.sh/article/llm-observability-pricing
- kosmoy.com Langfuse alternatives: https://www.kosmoy.com/resources/blog/langfuse-alternatives
- langwatch.ai LLM observability tools: https://langwatch.ai/blog/top-10-llm-observability-tools-complete-guide-for-2026
- finout.io AI cost observability: https://www.finout.io/blog/best-ai-cost-observability-tools-in-2026
- copilot-experts.com AI cost optimization: https://copilot-experts.com/best-ai-cost-optimization-tools
- helicone.ai blog: https://www.helicone.ai/blog/monitor-and-optimize-llm-costs
- portkey.ai cost management: https://portkey.ai/for/manage-and-attribute-costs
- legacyleap.ai AI gateway: https://www.legacyleap.ai/blog/genai-modernization-ai-gateway-architecture
- tensorzero.com blog: https://www.tensorzero.com/blog

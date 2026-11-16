# CREST 1.1 — provider guide

## Adapters

| Provider | Kind | Validation status |
| --- | --- | --- |
| Offline mock | `mock` | Fully validated; default, no network |
| Google Gemini | `gemini` | Adapter implemented; **not live-validated** (no authorized account/live calls used) |
| OpenAI-compatible | `openai_compatible` | Adapter implemented; validated against a **local loopback** HTTP test server only |

## Adding a provider

1. In **Settings**, explicitly enable **Allow external provider calls**. This is
   off by default and never turns itself on.
2. In **Providers → Configure**, set the base URL, models, default model,
   pricing (optional), timeout, **max retries (0–5)** and **rate limit/minute**.
3. Use **Set key** to store the API key. It is protected with Windows DPAPI and
   cannot be viewed again. The `api_key_env` field remains as an environment
   fallback (used only when no stored credential exists).
4. Press **Test connection** for an explicit, minimal request, or
   **Discover models** to fetch the remote model list into the form. Both are
   confirm-only actions and record usage rows.

## Failure handling

- Transient failures (timeouts, 429, 5xx, connection errors) get bounded retries
  with exponential-ish backoff and honor `Retry-After` when supplied.
- A local per-provider rate limiter enforces the lower of the provider limit and
  the global setting; exceeding it is reported, not silently ignored.
- Cancellation is checked during backoff and pause waits, so **Stop all** and
  **Pause** take effect promptly.
- Errors are sanitized: the API key is replaced before the message is stored or
  returned. Usage history records status, tokens, cost, and latency — never a secret.

## Usage history

**Providers → Provider usage history** shows calls, token totals, recorded
cost, latency, and error status. Cost is $0 when pricing is not configured;
this is labelled in the UI rather than presented as a measurement.

## Honest limits

No live Gemini or paid OpenAI call was made in this release. Cost figures
depend on pricing you enter. Provider validation used a local mock server only;
do not assume billing behaviour has been verified.

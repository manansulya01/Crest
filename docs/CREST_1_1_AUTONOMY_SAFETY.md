# CREST 1.1 — autonomy and safety guide

CREST separates **autonomy level** (what a task may attempt, levels 1–5) from
**operating mode** (the global stance). Both are enforced in the backend before
every provider call; the UI cannot weaken either.

## Operating modes

| Mode | Behavior |
| --- | --- |
| **Manual** | Provider calls, recovery, adaptation, and export each require explicit approval. |
| **Supervised** (default) | Low-risk work runs; medium/high-risk provider calls route to approval. |
| **Bounded autonomous** | Explicitly permitted low/medium work runs inside budgets, timeouts, retries, and permissions. **High-risk actions stay gated.** |

An unknown mode fails closed. Changing modes writes an audit event.

## Controls that no mode can remove

- Autonomy ceiling (`max_autonomy_level`) checked at creation and each step.
- Task-level risk class and custom policy (which may only narrow permissions).
- Global external-call switch and external-call approval requirement.
- Budget, token, and timeout pre-flight and post-call checks.
- Deterministic verification before acceptance.
- **Strong High-Risk Gate**: high-risk acceptance needs independent evidence;
  mock-only evidence abstains by design.
- Approval tokens bound to a policy fingerprint; edits invalidate them.

## Pause and stop

**Pause** persists in settings and blocks new executions; running work stops at
its next cancellation checkpoint and resumes when cleared. **Stop all** cancels
pending/running/awaiting-approval tasks and records an audit event. Completed
work and evidence are never deleted by these controls.

## Recommended posture for daily use

- Start in **Supervised** with external calls disabled.
- Keep the global autonomy ceiling at **Level 3** unless you have a specific reason.
- Leave high-risk approval and external-call approval enabled.
- Export a JSON backup before changing resilience or provider settings.
- Review the approval queue daily; approve only after reading the reason and evidence.

CREST remains Level 3 — supervised personal use, not a production safety guarantee.

# CREST 1.1 — user manual

## First run

On first launch a short wizard explains the local-first posture, asks you to
choose an **operating mode** (Manual, Supervised, or Bounded autonomous), and
confirms the safety scope. Nothing is sent anywhere. You can change the mode
later in **Autonomy**.

## Daily workflow

1. **Tasks → New task.** Pick a risk class, autonomy level, provider/model,
   budget, token budget, timeout, and acceptance criteria.
2. **Execute.** Low-risk work runs immediately in Supervised mode. Actions that
   need approval appear in **Approvals** with the exact reason and policy
   fingerprint; approve or reject there.
3. **Review evidence.** Task detail shows the plan, steps, evidence, gate
   decision, cost, and full audit trail. A failed verification is reported as
   failed — never as completed. High-risk work abstains when independent
   evidence is insufficient.
4. **Export or report** a single task as JSON when you need a record.

## Global controls (top bar)

| Control | Behavior |
| --- | --- |
| Mode badge | Current server-enforced operating mode; click to change it |
| Pause / Resume | New executions are blocked; already-running work stops at the next checkpoint. Persisted across restarts |
| Stop all | Cancels pending, running, and awaiting-approval tasks; never deletes history |
| Theme | Persistent light/dark preference |

## Pages

- **Dashboard / Tasks / Approvals** — day-to-day work
- **Autonomy** — operating mode, global ceiling, permission matrix
- **Providers** — endpoints, models, retries, rate limits, credentials, usage history
- **Routing / Budgets / Evidence / Audit** — policy and verification detail
- **Settings** — defaults, safety switches, resilience, backup/retention, CSRF/bearer token
- **System** — paths, schema version, credentials, logs, database integrity

## Keyboard and accessibility

Every control is reachable by keyboard; dialogs close with Escape (except the
mandatory first-run wizard). Status is conveyed with text and colour, never by
colour alone. The layout collapses to a single column on narrow windows.

## Credentials

Add keys in **Providers → Set key**. They are encrypted with Windows DPAPI for
the current Windows account, stored as ciphertext in the local database, and
never returned, logged, or exported. Clearing a key removes the ciphertext.
Environment-variable keys remain supported as a fallback for advanced users.

## Safety reminder

CREST is Level 3 — supervised personal use. Evidence is content-addressed but
not cryptographically signed. Keep meaningful decisions under human review.

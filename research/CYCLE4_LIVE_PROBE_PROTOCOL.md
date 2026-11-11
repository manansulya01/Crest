# Cycle 4 — Live Probe Protocol (NOT EXECUTED)

**Status:** Design only. No live calls. No spending. Authorization required before execution.

## 1. Research question

Does a risk-adaptive execution gate reduce harmful acceptance decisions when
generator and verifier errors are correlated in real model outputs?

## 2. Candidate provider and model

- Provider: Google (Gemini) — only `GEMINI_API_KEY` is available in this environment.
- Model: `gemini-3.5-flash-lite` (candidate; verify current availability and pricing before execution).
- The previously unavailable strong model (`gemini-3.8-flash`) must not be used unless its availability is independently established. No silent substitution.
- If the candidate is unavailable, report that fact and stop.

## 3. Task set

- 10–20 tasks from categories A (arithmetic) and C (classification) only.
- Objectively checkable answers.
- No personal or sensitive data.
- No private repository contents sent to the provider.

## 4. Prompts

- Generator prompt: "Solve the following task. Output only the answer."
- Verifier prompt: "Is the following answer correct? Output CORRECT or INCORRECT."
- Exact prompt templates recorded with hashes.

## 5. Generation settings

- Temperature 0.0 (deterministic) for both generator and verifier.
- Max tokens: 256 (generator), 16 (verifier).
- No system prompt beyond the task instruction.

## 6. Estimated cost

- ~100 tokens per task × 2 calls (generator + verifier) = 200 tokens/task.
- 20 tasks × 200 tokens = 4000 tokens.
- At ~$0.0001/token (flash-lite pricing, verify before execution): ~$0.40.
- **Maximum allowed cost: $0.05.** The probe must be reduced to fit: 10 tasks × 2 calls × ~100 tokens = 2000 tokens ≈ $0.20. Further reduce to 5 tasks if needed to stay under $0.05.
- Stop immediately if estimated cost exceeds $0.05.

## 7. Ground truth

- Arithmetic: independently compute the expected result.
- Classification: predefined label.
- No LLM judge as ground truth.

## 8. Data handling

- Record only: task ID, generator output, verifier output, ground-truth label, model ID, prompt hash, token counts.
- Do not store raw provider metadata unless needed.
- No API keys in artifacts.

## 9. Stop conditions

- Cost exceeds $0.05.
- Provider returns an error or rate limit.
- Model is unavailable.
- Any unexpected behavior (e.g., refusal, empty output).

## 10. What this probe can and cannot prove

- **Can prove:** feasibility of the harness, obvious model failures, whether the verifier shares failure modes with the generator (qualitatively).
- **Cannot prove:** reliable error rates, statistically significant FAR reduction, or independence of errors. A 10–20 task sample is a feasibility check, not a validation.<|end|>
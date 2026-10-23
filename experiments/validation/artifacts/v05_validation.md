# Crest V0.5 independent validation result

This file is generated from `experiments/validation/artifacts/v05_validation.json`.
It reports a synthetic recovery-admission experiment, not model-provider
economics and not a production safety guarantee.

- Protocol SHA-256: `9e34242e86d9cb1c226cdc21679499c6da9042cd1771ec0150daeccab2086020`
- Result digest: `f5ee354ba3ac92319ffb13715b977de582a13d66a3a89532632ebc465d600767`
- Commit: `0ee0af795d1844b25085aaaed3c3c8da7d5aae99`
- Working tree dirty: `False`
- Canonical config digest: `34a98f8ba90ad127d3512350cd42e3992e1c703b6b201688aa70d60ad72d1fcf`
- Verdict: **PASS**

## Policy summary

| policy | admitted | unsafe | reliable admitted | false rejects | precision | unsafe rate (admitted) |
|---|---:|---:|---:|---:|---:|---:|
| deny_all | 0 | 0 | 0 | 10 | None | None |
| admit_all | 42 | 32 | 10 | 0 | 0.238095 | 0.761905 |
| fixture_only | 16 | 6 | 10 | 0 | 0.625 | 0.375 |
| family_only | 10 | 0 | 10 | 0 | 1.0 | 0.0 |
| generalized | 10 | 0 | 10 | 0 | 1.0 | 0.0 |
| oracle | 10 | 0 | 10 | 0 | 1.0 | 0.0 |

## Paired safety comparison

- Fixture-only unsafe / generalized safe: 6
- Generalized unsafe / fixture-only safe: 0
- Exact McNemar two-sided p: 0.03125
- One-sided safety p: 0.015625

## Decision

- H1 safety: **PASS**
- H2 reliable coverage: **PASS**
- H3 evidence precision: **PASS**

The oracle row is a diagnostic upper bound using evaluation labels; it is
not a deployable policy. Verification seconds are wall-clock observations
and are excluded from the scientific digest.

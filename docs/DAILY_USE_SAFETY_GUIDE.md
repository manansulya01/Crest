# CREST Daily Use Safety Guide

## Permitted use

CREST is safe for:
- Local development and experimentation.
- Supervised personal use with explicitly approved operations.
- Research and benchmarking.
- Offline evaluation of AI execution strategies.

## Prohibited use

Do NOT use CREST for:
- Unsupervised autonomous operation on sensitive files.
- Production systems handling real user data.
- Financial, medical, or safety-critical decisions.
- Multi-user or multi-tenant deployments.
- Any operation where a security failure would cause harm.

## Safety rules

1. Always run `crest doctor` before use.
2. Keep workspace permissions restricted.
3. Never store real API keys in `crest.yaml` or `.crest/`.
4. Review audit logs after every session (`crest audit`).
5. Back up `.crest/` state before experiments.
6. Do not disable admission checks.
7. Do not use dev keys in production.
8. Set conservative budgets in `crest.yaml`.
9. Revoke capabilities immediately after use (`crest revoke`).
10. Report any unexpected behavior.
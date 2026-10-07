# Crest

Crest is an execution control plane for AI agents that grants autonomous tool
capabilities only when independently verified recovery evidence and
constitutional exposure limits justify the action.

> Learning proposes. Evidence certifies. The constitution grants. Observation
> can revoke.

**Crest does not provide unconditional safety guarantees.** Its evidence and
exposure guarantees are conditional on the validity and scope of the
verifier, evidence model, environment assumptions, and constitutional policy.
In V0.4 the strongest evidence class Crest can grant is measured over specific
environment families and distributions — not over "the real world".

```text
agent request -> CrestRuntime.check/execute -> admission decision -> adapter (fs/git/shell) -> audit
```

## What it enforces

- Deterministic admission over persisted capabilities, receipts, exposure budget, scope
- Content-addressed receipts validated before execution
- Append-only audit and SQLite persistence
- Revocation that is immediate; re-admission requires fresh verification
- Fail-closed on corrupt state, unknown tools, scope violations, budget exhaustion

## Install / first run

```bash
pip install -e .
cd your-project
crest init --root .
crest verify --action modify_file --recovery restore_from_snapshot --target README.md --scope '*'
crest exec filesystem modify_file --arg path=README.md --arg content='hello'
crest status
crest audit
crest policy check --tool filesystem --operation delete_file --arg path=README.md
```

Full demo of the full pipeline incl. revocation: `python examples/runtime_demo.py`

## Direct SDK use

```python
from crest.runtime import CrestRuntime
from crest.gateway import ToolGateway, ToolRequest

rt = CrestRuntime.from_config("crest.yaml")
gw = ToolGateway(rt)
r = gw.execute(ToolRequest(agent_id="agent-1", tool="filesystem", operation="modify_file",
                           arguments={"path": "a.txt", "content": "x"}))
# r.ok / r.reason / r.exposure_after / audit persisted
```

## V0.4 — generalized evidence, cross-distribution evaluation, honest statistics

- **Independent holdout generator** (`crest.holdout_gen`) — structurally
  different from the training fixture generator.
- **Distributions** (`crest.distributions`) — in-distribution, parameter,
  structural, adversarial, composition, out-of-family.
- **Policy-driven evidence classes** (`crest.policy`) — Wilson upper bounds,
  configurable confidence, small-sample guards; observed failures ⇒
  `UNVERIFIED` (fixing a V0.3 conflation).
- **Replay protection** — revoking a capability revokes its receipt.
- **Receipt v2** — versioned schema, canonical serialization, payload/evidence
  digests, Ed25519 signature over the canonical payload (dev keys in
  `.crest/keys/`; production key custody external).
- **Migrations** with history, crash-consistency tests, MCP-style gateway,
  secret redaction, `crest doctor` with ERROR/WARNING/INFO, `crest experiment`
  runners for every research artifact.

Research findings and limitations: `docs/research-v0.4.md`,
`docs/security-review-v0.4.md`.

## V0.3 generalized evidence

Receipts are graded into evidence classes: `VERIFIED_FIXTURE`,
`VERIFIED_FAMILY`, `VERIFIED_GENERAL`. A `GeneralizationVerifier` runs
recovery across fixture seeds and a hidden holdout split; classification only
strengthens when holdout coverage is sufficient. Admission rejects fixture
receipts whenever `min_evidence_class` is stricter than the receipt's class.
Drift detection compares evidence-family invariants against the real
workspace. See `docs/research-v0.3.md` and
`python examples/generalized_evidence_demo.py`.

New CLI surface: `crest verify-generalized`, `crest evidence list`,
`crest doctor`, `crest benchmark`, `crest report`, `crest exec --dry-run`,
`crest experiment {cross-distribution,ablations,exposure-sweep,confidence,drift,tables,conclusion,holdout}`.

## Research lineage and honest boundary

Milestones 1–2 (in this repo or merged from `experiment/milestone2-falsification`)
demonstrated: admission works mechanically, but verification covers the tested
fixture, not arbitrary unseen environments. Crest Runtime v0 is therefore
conservative: shields are real, guarantees are conditional on evidence that
ignores environment fidelity until it is improved.

Do not treat a receipt as a claim of general recoverability.

## Layout

```
src/crest/
  agent_runtime.py   product runtime (CrestRuntime)
  capabilities.py    Capability state machine
  constitution.py    policy dataclass (frozen)
  config.py          crest.yaml loader + defaults
  paths.py           canonical path + scope matching (Windows-aware)
  store.py           SQLite persistence (fail-closed)
  audit JSONL mirror under .crest/audit.jsonl
  receipts.py        CapabilityReceipt (content-addressed)
  verifier.py        independent deterministic verifier
  ledger.py          exposure ledger (research engine)
  adapters/          filesystem, git, shell
  cli.py             argparse CLI
  gateway.py         ToolGateway / ToolRequest / ToolResult
  runtime.py         research runtime + CrestRuntime re-export
experiments/         milestone 2 experiments (adapters reuse the same primitives)
tests/               unit / security / adapters / persistence / cli / integration
```

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

## CREST 1.0 product layer

CREST 1.0 ships a local-first product on top of the research runtime:

- **Product site** at `/`, app at `/app`, OpenAPI docs at `/api/docs`
- **FastAPI backend** (`crest.api:app`) with server-enforced autonomy,
  permissions, budgets, approvals, verification, recovery, audit, and the
  Strong High-Risk Gate
- **React web app** with 14 app pages, light/dark themes, and real backend data
- **Offline mock provider** that exercises success, verification failure,
  recovery, budget exhaustion, observe-mode denial, assisted approval,
  high-risk abstention, and custom-policy denial without network calls
- **Browser-based desktop launcher** (`crest_desktop.py`) — not a native package
- **39 product tests** plus the existing research test suite

### Quickstart

```bash
pip install -e ".[product]"

cd web
npm install
npm run build
cd ..

python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/app>. No provider keys are required. External
provider calls and spending are disabled by default; the tested execution path
is the offline mock provider.

Or run `python crest_desktop.py` to start the server and open the app in your
default browser.

### Product documentation

- [`docs/PRODUCT_GUIDE.md`](docs/PRODUCT_GUIDE.md) — concepts, autonomy,
  budgets, approvals, verification, gate, offline demos
- [`docs/PRODUCT_API.md`](docs/PRODUCT_API.md) — HTTP API reference
- [`docs/PRODUCT_ARCHITECTURE.md`](docs/PRODUCT_ARCHITECTURE.md) — product
  architecture and persistence
- [`docs/PRODUCT_OPERATIONS.md`](docs/PRODUCT_OPERATIONS.md) — install, run,
  backup, upgrade, troubleshooting
- [`docs/PRODUCT_COMPLETION_TRACKER.md`](docs/PRODUCT_COMPLETION_TRACKER.md) —
  requirement-by-requirement validation record
- [`docs/CREST_1_0_INSTALLATION.md`](docs/CREST_1_0_INSTALLATION.md) —
  installation guide

### Honest limits

CREST 1.0 is Level 3 — supervised personal use, not a multi-tenant production
service. Evidence is content-addressed but not signed. Live external providers
were not validated in this release. The desktop launcher is browser-based. The
Strong High-Risk Gate abstains on high-risk tasks when independent evidence is
insufficient; with mock-only evidence it will abstain by design.

## Research runtime (preserved)

The sections below describe the original research runtime, its evidence model,
benchmarks, experiments, and historical results. They remain part of the
repository and are not replaced by the product layer.

## What it enforces

- Deterministic admission over persisted capabilities, receipts, exposure budget, scope
- Content-addressed receipts validated before execution
- Append-only audit and SQLite persistence
- Revocation that is immediate; re-admission requires fresh verification
- Fail-closed on corrupt state, unknown tools, scope violations, budget exhaustion
- Scope drift detection (target must remain within admitted scope)

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

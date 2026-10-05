# Crest runtime: execution control plane for agents.

Agents propose. The constitution grants.

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

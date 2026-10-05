# Development

```
pip install -e ".[dev]"
python -m pytest
python examples/runtime_demo.py
python -m experiments.runners.run_experiment --matrix --latency-bound-ms 50
python experiments/holdout/run_holdout.py
```

Source layout, SDKs, and public API are in `docs/architecture.md` and the
package docstrings. Public entry points: `CrestRuntime`, `ToolGateway`,
`crest.cli.main`.

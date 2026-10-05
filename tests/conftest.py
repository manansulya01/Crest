import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
import yaml

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig


def make_runtime(tmp_path: Path, **overrides) -> CrestRuntime:
    cfg = CrestConfig(
        workspace_root=tmp_path,
        state_dir=tmp_path / ".crest",
        **overrides,
    )
    return CrestRuntime(cfg)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.txt").write_text("hello", encoding="utf-8")
    return tmp_path

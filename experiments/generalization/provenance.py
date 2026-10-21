"""Scientific-content hashing for reproduction manifests.

Raw experiment files contain two kinds of information:

* scientific content: parameters, sample counts, classifications, success
  rates, admissions, detected drift, and failures;
* observational metadata: run timestamps, wall-clock costs/latencies,
  git/environment identifiers, and the order in which a machine happened to
  emit them.

The canonical content digest must ignore the second class while changing
whenever the first class changes. This module is the single definition of
that boundary. Raw file hashes are still recorded separately by the CLI for
artifact-integrity checks and for the performance-record digest.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

# Keys excluded from the scientific-content digest. Most are wall-clock
# observations; the rest are run/machine provenance already recorded in the
# manifest. Keys that affect experiment behavior/config (for example
# ``config_digest``, ``canonical``, ``seed_base``, ``n``) are retained.
VOLATILE_KEYS = frozenset(
    {
        "timestamp",
        "generated_at",
        "verification_seconds",
        "seconds",
        "revocation_latency_ms",
        "git_commit",
        "branch",
        "os",
        "python",
        "python_version",
        "crest_version",
        "verifier_version",
    }
)

TIMING_KEYS = frozenset(
    {"verification_seconds", "seconds", "revocation_latency_ms"}
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def normalize_json(value: Any) -> Any:
    """Remove volatile keys recursively, preserving scientific structure."""
    if isinstance(value, dict):
        return {
            key: normalize_json(item)
            for key, item in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    return value


def _load_jsonl(path: Path | str) -> list[dict[str, Any]] | None:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    rows = []
    try:
        for line in text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, TypeError):
        return None
    return rows


def scientific_jsonl_digest(path: Path | str) -> str | None:
    """Digest a JSONL source after removing volatile/observational fields."""
    rows = _load_jsonl(path)
    if rows is None:
        return None
    return sha256_text(canonical_json(normalize_json(rows)))


def timing_values(path: Path | str) -> dict[str, list[Any]]:
    """Collect wall-clock measurements from a JSONL source, by key name."""
    rows = _load_jsonl(path)
    if rows is None:
        return {}

    collected: dict[str, list[Any]] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in TIMING_KEYS:
                    collected.setdefault(key, []).append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(rows)
    return {key: collected[key] for key in sorted(collected)}


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_markdown_separator(cells: list[str]) -> bool:
    return bool(cells) and all(
        cell and set(cell) <= set("-: ") for cell in cells
    )


def normalize_markdown_table(text: str) -> str:
    """Strip provenance comments and replace timing cells with a marker.

    Timing columns are identified by their headers (``cost``/``latency``),
    so the rule also works for the combined ``all_tables.md`` file.
    """
    lines = text.splitlines()
    output: list[str] = []
    timing_columns: set[int] = set()

    for index, line in enumerate(lines):
        if line.startswith("<!-- crest-table"):
            continue
        if line.startswith("|"):
            cells = _split_markdown_row(line)
            next_is_separator = (
                index + 1 < len(lines)
                and lines[index + 1].startswith("|")
                and _is_markdown_separator(_split_markdown_row(lines[index + 1]))
            )
            if next_is_separator:
                timing_columns = {
                    position
                    for position, cell in enumerate(cells)
                    if "cost" in cell.lower() or "latency" in cell.lower()
                }
                output.append(line)
                continue
            if _is_markdown_separator(cells):
                output.append(line)
                continue
            if timing_columns:
                for position in timing_columns:
                    if position < len(cells):
                        cells[position] = "<timing>"
                output.append("| " + " | ".join(cells) + " |")
                continue
        output.append(line)

    normalized = "\n".join(output)
    if text.endswith("\n"):
        normalized += "\n"
    return normalized


def normalize_csv_table(text: str) -> str:
    """Replace timing columns in a CSV table while preserving structure."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    timing_columns = {
        position
        for position, cell in enumerate(rows[0])
        if (
            cell in TIMING_KEYS
            or "second" in cell.lower()
            or "latency" in cell.lower()
        )
    }
    normalized = [rows[0]]
    for row in rows[1:]:
        cells = list(row)
        for position in timing_columns:
            if position < len(cells):
                cells[position] = "<timing>"
        normalized.append(cells)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(normalized)
    return buffer.getvalue()


def scientific_artifact_digest(name: str, text: str) -> str:
    """Digest a generated table with timing cells and provenance removed."""
    # Make the content digest independent of the checkout's line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if name.endswith(".md"):
        normalized = normalize_markdown_table(text)
    elif name.endswith(".csv"):
        normalized = normalize_csv_table(text)
    else:
        normalized = text
    return sha256_text(normalized)

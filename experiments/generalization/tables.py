"""Generate research tables (Markdown + CSV) from experiment JSONL artifacts.

No numbers are invented: every cell comes from a result file under
experiments/results/.

Generation is separated from writing:

* ``build_all`` is pure: it reads the source JSONL files and returns the
  rendered table texts, raising:
  - ``MissingResultsError`` when a source file is absent or empty,
  - ``NonCanonicalResultsError`` when a source records a configuration that
    differs from the canonical configuration (reduced or overridden runs),
  - ``TableValidationError`` when rendering or validation fails.
* ``write_all`` builds, validates, stages into a temporary directory inside
  the destination and then replaces the destination files. A failure before
  replacement leaves the existing artifacts untouched.

Canonical tables are only replaced when every source artifact records the
canonical configuration from experiments/configs/experiment.yaml; reduced
runs must not silently overwrite them (override with
``allow_noncanonical=True`` / ``--allow-noncanonical``, which marks the
generated tables as non-canonical).

Every generated Markdown table carries a provenance comment with the table
schema version, the canonical configuration digest, and the sha256 of each
source artifact; the digest covers actual file bytes. The CSV mirrors the
ablation rows without a provenance comment (CSV has no comment syntax);
provenance for it lives in the manifest and in ablations.md.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .config import canonical

RESULTS = Path(__file__).resolve().parents[1] / "results"
TABLES = Path(__file__).resolve().parents[1] / "tables"

TABLE_SCHEMA = 1

# Source artifacts consumed by table generation, in load order.
SOURCES = (
    "cross_distribution.jsonl",
    "ablations.jsonl",
    "exposure_sweep.jsonl",
    "confidence_sensitivity.jsonl",
    "drift.jsonl",
)


class MissingResultsError(RuntimeError):
    """A source artifact required for table generation is absent or empty."""


class NonCanonicalResultsError(RuntimeError):
    """A source artifact records a non-canonical (reduced/overridden) run."""


class TableValidationError(RuntimeError):
    """Generated table content failed validation; nothing was written."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------------
# canonicality of the recorded sources
# --------------------------------------------------------------------------

def _canonical_problems(loaded: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Compare each source's recorded configuration to the canonical one."""
    cfg = canonical()
    digest = cfg.digest()
    problems: list[str] = []

    def check_digest(
        name: str, config: dict[str, Any], index: int | None = None
    ) -> bool:
        where = name if index is None else f"{name} row {index}"
        recorded = config.get("config_digest")
        if recorded != digest:
            problems.append(
                f"{where} records config_digest={recorded!r}, canonical is {digest}"
            )
            return False
        return True

    abl = loaded["ablations.jsonl"][0].get("config") or {}
    if abl.get("canonical") is not True:
        problems.append(
            f"ablations.jsonl records canonical={abl.get('canonical')!r}"
        )
    if abl.get("cases_per_measurement") != cfg.samples:
        problems.append(
            "ablations.jsonl records cases_per_measurement="
            f"{abl.get('cases_per_measurement')!r}, canonical is {cfg.samples}"
        )
    if abl.get("maximum_failure_upper_bound") != cfg.maximum_failure_upper_bound:
        problems.append(
            "ablations.jsonl records maximum_failure_upper_bound="
            f"{abl.get('maximum_failure_upper_bound')!r}, canonical is "
            f"{cfg.maximum_failure_upper_bound}"
        )
    check_digest("ablations.jsonl", abl)

    conf = loaded["confidence_sensitivity.jsonl"][0]
    if conf.get("canonical") is not True:
        problems.append(f"confidence_sensitivity.jsonl records canonical={conf.get('canonical')!r}")
    if conf.get("n") != cfg.confidence_samples:
        problems.append(
            "confidence_sensitivity.jsonl records n="
            f"{conf.get('n')!r}, canonical is {cfg.confidence_samples}"
        )
    check_digest("confidence_sensitivity.jsonl", conf)

    cross_rows = loaded["cross_distribution.jsonl"]
    cross_flags = {
        (row.get("config") or {}).get("canonical") for row in cross_rows
    }
    if cross_flags != {True}:
        problems.append(
            f"cross_distribution.jsonl records canonical={sorted(cross_flags, key=repr)}"
        )
    for index, row in enumerate(cross_rows, 1):
        cross = row.get("config") or {}
        samples = cross.get("samples_per_distribution")
        if not isinstance(samples, dict) or any(
            value != cfg.cross_distribution_samples
            for value in samples.values()
        ):
            problems.append(
                f"cross_distribution.jsonl row {index} records "
                f"samples_per_distribution={samples!r}, canonical is "
                f"{cfg.cross_distribution_samples} per distribution"
            )
            break
        if not check_digest("cross_distribution.jsonl", cross, index=index):
            break

    sweep = loaded["exposure_sweep.jsonl"][0]
    if sweep.get("canonical") is not True:
        problems.append(f"exposure_sweep.jsonl records canonical={sweep.get('canonical')!r}")
    check_digest("exposure_sweep.jsonl", sweep)

    drift = loaded["drift.jsonl"][0]
    if drift.get("canonical") is not True:
        problems.append(f"drift.jsonl records canonical={drift.get('canonical')!r}")
    if drift.get("cases_per_class") != cfg.drift_cases_per_class:
        problems.append(
            "drift.jsonl records cases_per_class="
            f"{drift.get('cases_per_class')!r}, canonical is {cfg.drift_cases_per_class}"
        )
    check_digest("drift.jsonl", drift)

    return problems


# --------------------------------------------------------------------------
# rendering (pure)
# --------------------------------------------------------------------------

def _provenance(source_hashes: dict[str, str], canonical_sources: bool) -> str:
    sources = ";".join(
        f"{name}=sha256:{digest}" for name, digest in sorted(source_hashes.items())
    )
    return (
        f"<!-- crest-table schema={TABLE_SCHEMA} "
        f"config_digest={canonical().digest()} "
        f"canonical={'true' if canonical_sources else 'false'} "
        f"sources={sources} -->"
    )


def _cross_distribution_table(rows: list[dict[str, Any]]) -> str:
    dist_keys = list(rows[0]["distributions"].keys())
    header = "| action | family | recovery | " + " | ".join(dist_keys) + " |"
    sep = "|---|---|---|" + "---|" * len(dist_keys)
    out = [header, sep]
    for r in rows:
        cells = [f"{r['distributions'][k]['success_rate']:.2f}" for k in dist_keys]
        out.append(
            f"| {r['action']} | {r['family']} | {r['recovery_kind']} | "
            + " | ".join(cells)
            + " |"
        )
    return "\n".join(out) + "\n"


def _ablation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows[0]["results"] if rows and "results" in rows[0] else rows


def _ablation_table(abl: list[dict[str, Any]]) -> str:
    out = [
        "| mode | action | family | recovery | evidence class | admitted | "
        "eval success | false admission | false rejection | cost (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in abl:
        out.append(
            f"| {r['mode']} | {r['action']} | {r['family']} | {r['recovery']} | "
            f"{r['evidence_class']} | {r['admitted']} | {r['evaluation_success']:.2f} | "
            f"{r['false_admission']} | {r['false_rejection']} | {r['verification_seconds']} |"
        )
    return "\n".join(out) + "\n"


def _ablation_csv(abl: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(abl[0].keys()))
    writer.writeheader()
    writer.writerows(abl)
    return buffer.getvalue()


def _exposure_sweep_table(rows: list[dict[str, Any]]) -> str:
    out = [
        "| E_max | executed | denied | certified exposure | AAC | GAC |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['e_max']} | {r['executed']} | {r['denied']} | "
            f"{r['certified_exposure']} | {r['aac']} | {r['gac']} |"
        )
    return "\n".join(out) + "\n"


def _confidence_table(rows: list[dict[str, Any]]) -> str:
    out = [
        "| confidence | action | family | recovery | evidence class | admitted | "
        "eval success | false admission |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| {r['confidence']} | {r['action']} | {r['family']} | {r['recovery']} | "
            f"{r['evidence_class']} | {r['admitted']} | {r['evaluation_success']:.2f} | "
            f"{r['false_admission']} |"
        )
    return "\n".join(out) + "\n"


def _drift_table(record: dict[str, Any]) -> str:
    out = [
        "| drift class | detected | implementation | detection latency (ms) | reason |",
        "|---|---|---|---|---|",
    ]
    for o in record["outcomes"]:
        lat = o["revocation_latency_ms"]
        out.append(
            f"| {o['drift_class']} | {o['detected']} | {o['implementation']} | "
            f"{lat if lat is not None else '-'} | {o['detection_reason'][:48]} |"
        )
    out.append("")
    out.append("summary: " + json.dumps(record["summary"]))
    return "\n".join(out) + "\n"


def build_all(
    *,
    results_dir: Path | str | None = None,
    allow_noncanonical: bool = False,
) -> dict[str, str]:
    """Render every table from the source artifacts; return {filename: text}.

    Raises ``MissingResultsError`` when a source is absent or empty,
    ``NonCanonicalResultsError`` when a source is not canonical (unless
    allowed) and ``TableValidationError`` when rendering fails validation.
    Never writes anything.
    """
    rdir = Path(results_dir) if results_dir is not None else RESULTS
    loaded: dict[str, list[dict[str, Any]]] = {}
    for name in SOURCES:
        path = rdir / name
        if not path.is_file():
            raise MissingResultsError(
                f"required source artifact is missing: {path}; run a full "
                "canonical reproduction (crest research reproduce --full) first"
            )
        rows = _load(path)
        if not rows:
            raise MissingResultsError(
                f"required source artifact is empty: {path}; run a full "
                "canonical reproduction (crest research reproduce --full) first"
            )
        loaded[name] = rows

    problems = _canonical_problems(loaded)
    if problems and not allow_noncanonical:
        raise NonCanonicalResultsError(
            "refusing to regenerate canonical tables from non-canonical "
            "results (the canonical tables would no longer match their "
            "recorded provenance): "
            + "; ".join(problems)
            + ". Re-run canonical full reproduction (crest research reproduce "
            "--full) without --samples, or pass allow_noncanonical=True to "
            "generate explicitly non-canonical tables."
        )

    source_hashes = {name: _sha256_file(rdir / name) for name in SOURCES}
    provenance = _provenance(source_hashes, canonical_sources=not problems)

    try:
        sections = {
            "cross_distribution.md": _cross_distribution_table(loaded["cross_distribution.jsonl"]),
            "ablations.md": _ablation_table(_ablation_rows(loaded["ablations.jsonl"])),
            "exposure_sweep.md": _exposure_sweep_table(loaded["exposure_sweep.jsonl"][0]["rows"]),
            "confidence_sensitivity.md": _confidence_table(loaded["confidence_sensitivity.jsonl"][0]["rows"]),
            "drift.md": _drift_table(loaded["drift.jsonl"][0]),
        }
        csv_text = _ablation_csv(_ablation_rows(loaded["ablations.jsonl"]))
    except (KeyError, TypeError, ValueError, csv.Error) as exc:
        raise TableValidationError(
            f"table generation failed on malformed results: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    files: dict[str, str] = {}
    combined = ["# Crest V0.4 result tables (generated)", ""]
    for name, body in sections.items():
        files[name] = provenance + "\n\n" + body
        combined.append(f"## {name[:-3].replace('_', ' ')}")
        combined.append(body)
    files["ablations.csv"] = csv_text
    files["all_tables.md"] = provenance + "\n\n" + "\n".join(combined)

    _validate(files, sections)
    return files


def _validate(files: dict[str, str], sections: dict[str, str]) -> None:
    required = {
        "cross_distribution.md",
        "ablations.md",
        "exposure_sweep.md",
        "confidence_sensitivity.md",
        "drift.md",
        "all_tables.md",
        "ablations.csv",
    }
    missing = required - set(files)
    if missing:
        raise TableValidationError(f"generated tables are incomplete: {sorted(missing)}")

    for name, text in files.items():
        if not text or not text.endswith("\n"):
            raise TableValidationError(f"generated table {name} is empty or unterminated")

    for name in sorted(required - {"ablations.csv"}):
        text = files[name]
        if not text.startswith("<!-- crest-table"):
            raise TableValidationError(f"generated table {name} lacks its provenance header")
        if sum(1 for line in text.splitlines() if line.startswith("|")) < 2:
            raise TableValidationError(f"generated table {name} contains no table rows")

    for title in sections:
        heading = f"## {title[:-3].replace('_', ' ')}"
        if heading not in files["all_tables.md"]:
            raise TableValidationError(f"all_tables.md is missing section {heading!r}")

    rows = list(csv.reader(io.StringIO(files["ablations.csv"])))
    if len(rows) < 2 or "mode" not in rows[0] or "evidence_class" not in rows[0]:
        raise TableValidationError("ablations.csv is malformed")


# --------------------------------------------------------------------------
# writing (validated, staged, replaced)
# --------------------------------------------------------------------------

def write_all(
    *,
    dest: Path | str | None = None,
    results_dir: Path | str | None = None,
    allow_noncanonical: bool = False,
) -> dict[str, Any]:
    """Generate, validate and replace tables; return a write summary.

    All files are staged inside a temporary directory under ``dest`` and only
    moved into place after every file has been generated and validated, so a
    failure leaves the previous artifacts untouched.
    """
    files = build_all(results_dir=results_dir, allow_noncanonical=allow_noncanonical)
    dest_dir = Path(dest) if dest is not None else TABLES
    dest_dir.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix=".crest-tables-new-", dir=str(dest_dir)))
    backup = Path(tempfile.mkdtemp(prefix=".crest-tables-old-", dir=str(dest_dir)))
    replaced: list[str] = []
    try:
        for name, text in files.items():
            (staging / name).write_text(text, encoding="utf-8", newline="\n")

        # Hash the bytes actually staged for replacement, then keep a copy of
        # every destination file that is about to be overwritten.
        hashes = {name: _sha256_file(staging / name) for name in files}
        for name in files:
            target = dest_dir / name
            if target.is_file():
                shutil.copy2(target, backup / name)

        for name in files:
            os.replace(staging / name, dest_dir / name)
            replaced.append(name)
    except Exception:
        # Roll back artifacts already replaced. A failure before the
        # replacement loop leaves every destination file untouched.
        for name in reversed(replaced):
            target = dest_dir / name
            previous = backup / name
            try:
                if previous.is_file():
                    os.replace(previous, target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)

    return {
        "dir": str(dest_dir),
        "files": sorted(files),
        "sha256": hashes,
        "config_digest": canonical().digest(),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Regenerate research tables from experiment results."
    )
    parser.add_argument("--dest", default=None, help="output directory (default: experiments/tables)")
    parser.add_argument(
        "--allow-noncanonical",
        action="store_true",
        help="write tables even if the stored results are reduced/overridden runs",
    )
    args = parser.parse_args()
    info = write_all(dest=args.dest, allow_noncanonical=args.allow_noncanonical)
    print(f"wrote {len(info['files'])} files into {info['dir']}: {', '.join(info['files'])}")

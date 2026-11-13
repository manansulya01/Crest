"""Verification for CREST 1.0 task outputs.

Verification is deterministic by default.  Optional provider verification is a
second, explicitly configured model call.  Evidence independence is recorded
honestly: a verifier only counts as independent when it is a different
provider or model from the generator.  The offline mock verifier is therefore
never counted as independent evidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_FAILURE_PHRASES = (
    "could not be completed",
    "unable to complete",
    "internal server error",
    "traceback (most recent call last)",
    "error:",
)
_MAX_OUTPUT_CHARS = 100_000


@dataclass
class VerificationResult:
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    has_deterministic_check: bool = False
    independent_sources: int = 0
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "has_deterministic_check": self.has_deterministic_check,
            "independent_sources": self.independent_sources,
            "failure_reason": self.failure_reason,
        }


def _check(
    name: str,
    *,
    passed: bool,
    detail: str,
    kind: str = "deterministic",
    required: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "status": "pass" if passed else "fail",
        "detail": detail,
        "required": required,
    }


def verify_output(
    task: dict[str, Any],
    text: str,
    *,
    verifier_result: dict[str, Any] | None = None,
) -> VerificationResult:
    checks: list[dict[str, Any]] = []
    output = text if isinstance(text, str) else ""

    checks.append(
        _check(
            "non_empty",
            passed=bool(output.strip()),
            detail="output is non-empty" if output.strip() else "output is empty",
        )
    )
    checks.append(
        _check(
            "length_limit",
            passed=len(output) <= _MAX_OUTPUT_CHARS,
            detail=f"{len(output)} characters (limit {_MAX_OUTPUT_CHARS})",
        )
    )
    lowered = output.lower()
    bad = next((phrase for phrase in _FAILURE_PHRASES if phrase in lowered), None)
    checks.append(
        _check(
            "failure_phrase",
            passed=bad is None,
            detail="no failure phrase detected" if bad is None else f"failure phrase detected: {bad!r}",
        )
    )

    if str(task.get("output_format") or "text") == "json":
        ok = False
        detail = "output is not valid JSON"
        try:
            parsed = json.loads(output)
            ok = isinstance(parsed, (dict, list))
            detail = "output is valid JSON" if ok else "JSON output must be an object or array"
        except (TypeError, ValueError) as exc:
            detail = f"invalid JSON: {exc}"
        checks.append(_check("json_valid", passed=ok, detail=detail))

    criteria = task.get("acceptance_criteria") or []
    if isinstance(criteria, str):
        try:
            criteria = json.loads(criteria)
        except ValueError:
            criteria = []
    for index, criterion in enumerate(criteria):
        criterion = str(criterion)
        name = f"criterion_{index + 1}"
        if criterion.startswith("contains:"):
            needle = criterion.split(":", 1)[1]
            checks.append(
                _check(name, passed=needle in output, detail=f"required substring: {needle!r}")
            )
        elif criterion.startswith("not_contains:"):
            needle = criterion.split(":", 1)[1]
            checks.append(
                _check(name, passed=needle not in output, detail=f"forbidden substring: {needle!r}")
            )
        elif criterion.startswith("regex:"):
            pattern = criterion.split(":", 1)[1]
            try:
                matched = re.search(pattern, output) is not None
                detail = f"regex matched: {pattern!r}" if matched else f"regex did not match: {pattern!r}"
            except re.error as exc:
                matched = False
                detail = f"invalid regex: {exc}"
            checks.append(_check(name, passed=matched, detail=detail))
        else:
            checks.append(
                _check(name, passed=criterion in output, detail=f"required text: {criterion!r}")
            )

    independent_sources = 0
    if verifier_result is not None:
        independent = bool(verifier_result.get("independent"))
        passed = bool(verifier_result.get("passed"))
        if passed and independent:
            independent_sources = 1
        checks.append(
            _check(
                "independent_verifier",
                passed=passed,
                detail=str(verifier_result.get("reason") or ("verifier passed" if passed else "verifier failed")),
                kind="independent_verifier",
            )
        )

    required = [c for c in checks if c["required"]]
    failed = [c for c in required if c["status"] != "pass"]
    passed = not failed
    deterministic = [c for c in checks if c["kind"] == "deterministic"]
    return VerificationResult(
        passed=passed,
        checks=checks,
        has_deterministic_check=bool(deterministic) and all(c["status"] == "pass" for c in deterministic),
        independent_sources=independent_sources,
        failure_reason="" if passed else f"{failed[0]['name']}: {failed[0]['detail']}",
    )


def build_verifier_prompt(task: dict[str, Any], output: str) -> str:
    criteria = task.get("acceptance_criteria") or []
    if isinstance(criteria, str):
        try:
            criteria = json.loads(criteria)
        except ValueError:
            criteria = []
    criteria_text = "\n".join(f"- {c}" for c in criteria) or "- No explicit criteria; judge whether the output answers the task."
    return (
        "You are an independent verifier for a task execution system.\n"
        "Do not rewrite the output. Judge it against the task and criteria.\n"
        f"TASK TITLE: {task.get('title')}\n"
        f"TASK DESCRIPTION: {task.get('description')}\n"
        f"RISK CLASS: {task.get('risk_class')}\n"
        f"ACCEPTANCE CRITERIA:\n{criteria_text}\n"
        "OUTPUT TO VERIFY:\n"
        f"{output[:20000]}\n\n"
        'Return only JSON: {"verdict":"PASS" or "FAIL","reason":"short explanation"}'
    )


def parse_verifier_output(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, re.S)
    if not match:
        return {"passed": False, "reason": "verifier response was not parseable JSON"}
    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return {"passed": False, "reason": "verifier response was not parseable JSON"}
    verdict = str(parsed.get("verdict") or "").strip().upper()
    reason = str(parsed.get("reason") or "").strip()[:500]
    if verdict not in ("PASS", "FAIL"):
        return {"passed": False, "reason": f"verifier returned unknown verdict: {verdict!r}"}
    return {"passed": verdict == "PASS", "reason": reason or verdict}

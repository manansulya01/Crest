"""Support-ticket structured-extraction workload (see docs/v0.7-benchmark-plan.md).

Deterministic, seeded generator. This is a synthetic evaluation set, not real
customer traffic. Gold labels are used only by the oracle scorer; routing
features are derived from task text alone (never from gold labels).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Mapping

SEED = 20261025

CATEGORIES = (
    "billing_refund",
    "access_request",
    "data_fix",
    "report_bug",
    "account_update",
    "general_help",
)
URGENCIES = ("routine", "urgent")
REFUNDS = ("yes", "no")

SPLIT_SIZES = {"calibration": 120, "pilot": 10, "heldout": 100}

PROMPT_SYSTEM = (
    "You extract fields from support tickets. Reply ONLY with a JSON object "
    "exactly of this schema and nothing else:\n"
    '{"category": ..., "urgency": ..., "refund_requested": ..., "due_date": ...}\n'
    "category is one of: billing_refund | access_request | data_fix | "
    "report_bug | account_update | general_help — based on the PRIMARY "
    "request stated in the ticket's first sentence, ignoring later mentions "
    "of other topics.\n"
    "urgency is one of: routine | urgent — per the explicit urgency language.\n"
    "refund_requested: yes | no — whether a payment rebate (refund) is asked for.\n"
    'due_date: the deadline exactly as YYYY-MM-DD if an explicit calendar '
    'date is given, otherwise the string "none".'
)

CAT_PHRASES = {
    "billing_refund": "Regarding an unexpected charge, I need help with my billing for {slot}.",
    "access_request": "I am writing to request access to {slot}.",
    "data_fix": "I need a correction made to my stored data because the record {slot}.",
    "report_bug": "I am reporting a software bug in your product: {slot}.",
    "account_update": "Please process an update to my account details for {slot}.",
    "general_help": "I am reaching out for general help with using your service, specifically {slot}.",
}

CAT_PREFIX = {cat: phrase.split("{slot}")[0] for cat, phrase in CAT_PHRASES.items()}

SLOT_TEXT = {
    "billing_refund": "my last invoice cycle",
    "access_request": "the analytics workspace edition",
    "data_fix": "contains entries that were never corrected since the import",
    "report_bug": "the layout overlaps the sidebar on wide screens",
    "account_update": "billing notifications",
    "general_help": "bulk export steps",
}

DISTRACTORS = {
    "billing_refund": "Also, my colleague asked about adjusting the data since one record looked wrong.",
    "access_request": "Additionally my teammate wanted to report a bug in the new release.",
    "data_fix": "Separately, someone requested access to another workspace earlier.",
    "report_bug": "By the way, a different team asked about modifying an account setting as well.",
    "account_update": "Note: yesterday we also glimpsed maybe a billing question about invoices.",
    "general_help": "One more thing — a friend was asking about requesting a refund too.",
}

URGENT_MARKERS = ("URGENT:", "as soon as possible", "immediately", "high priority")
ROUTINE_MARKERS = ("when convenient", "no rush", "at your earliest convenience")

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


@dataclass(frozen=True)
class Task:
    task_id: str
    split: str
    text: str
    gold: Mapping[str, str]
    multi_constraint: bool


@dataclass(frozen=True)
class RoutingFeatures:
    """Label-free features derived only from ticket text."""

    first_sentence_category_hint: str
    multi_topic: bool
    urgent_marker: bool
    deadline_phrase: bool
    refund_phrase: bool


def _rng(seed: int, index: int):
    import random

    return random.Random((seed * 7919 + index * 104729) & 0xFFFFFFFF)


def _iso_date(rng) -> str:
    year = 2026
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


TOPIC_KEYWORDS = {
    "billing_refund": ("refund", "rebate", "invoice", "charge back", "billing"),
    "access_request": ("access", "permission"),
    "data_fix": ("the data", "record", "correction"),
    "report_bug": ("bug", "defect"),
    "account_update": ("account", "profile"),
    "general_help": ("general help", "guidance", "how do i", "help with"),
}


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]


def _derive_first_sentence_category(text: str) -> str | None:
    first = _first_sentence(text).lower()
    for category, prefix in CAT_PREFIX.items():
        if prefix.lower() in first:
            return category
    return None


def detect_second_topic(text: str) -> str | None:
    """Label-free signal: the first sentence states the primary category (via
    its canonical phrase); a SECOND topic exists when a different category's
    keywords appear in the remainder of the text. Returns the second topic's
    category id or None."""
    primary = _derive_first_sentence_category(text)
    first_lower = _first_sentence(text).lower()
    remainder_lower = text.lower()[len(_first_sentence(text)):]
    for category, keywords in TOPIC_KEYWORDS.items():
        if category == primary:
            continue
        if any(keyword in remainder_lower for keyword in keywords) and not all(keyword in first_lower for keyword in keywords):
            return category
    return None


def derive_features(text: str) -> RoutingFeatures:
    first_hint = _derive_first_sentence_category(text)
    second_topic = detect_second_topic(text)
    return RoutingFeatures(
        first_sentence_category_hint=first_hint or "unknown",
        multi_topic=second_topic is not None,
        urgent_marker=any(marker.lower() in text.lower() for marker in URGENT_MARKERS),
        deadline_phrase=bool(re.search(r"by [A-Z][a-z]+ \d{1,2}, \d{4}|by \d{4}-\d{2}-\d{2}", text)),
        refund_phrase=bool(re.search(r"refund|rebate|charge back", text, re.IGNORECASE)),
    )


def _capabilities(features: RoutingFeatures) -> tuple[str, ...]:
    """Routing capability classes: text-derived only."""
    difficulty = "multi_topic" if features.multi_topic else "single_topic"
    return (difficulty,)


def generate_tasks(seed: int = SEED) -> tuple[Task, ...]:
    tasks: list[Task] = []
    total = sum(SPLIT_SIZES.values())
    for index in range(total):
        rng = _rng(seed, index)
        if index < SPLIT_SIZES["calibration"]:
            split = "calibration"
        elif index < SPLIT_SIZES["calibration"] + SPLIT_SIZES["pilot"]:
            split = "pilot"
        else:
            split = "heldout"
        category = CATEGORIES[rng.randrange(len(CATEGORIES))]
        urgency = URGENCIES[rng.randrange(len(URGENCIES))]
        if category == "billing_refund":
            refund = "yes" if rng.random() < 0.85 else "no"
        else:
            refund = "no" if rng.random() < 0.85 else "yes"
        has_date = rng.random() < 0.45
        due = _iso_date(rng) if has_date else "none"
        # 30% of tasks include a secondary-topic distractor sentence; the
        # actual multi-topic difficulty is re-derived from the final text so
        # generator intent and routing features cannot drift apart.
        add_distractor = rng.random() < 0.3

        urgency_phrase = rng.choice(URGENT_MARKERS) if urgency == "urgent" else rng.choice(ROUTINE_MARKERS)
        date_phrase = (
            f"Please make sure this is done by {_human_date(due)}." if has_date else ""
        )
        refund_phrase = ""
        if refund == "yes":
            refund_phrase = " I formally request a refund of the extra charge back to my card."
        parts = [
            f"{CAT_PHRASES[category].format(slot=SLOT_TEXT[category])}",
            refund_phrase,
            f"{date_phrase}",
            f"Handling level: {urgency_phrase}",
        ]
        body = " ".join(p for p in parts if p)
        if add_distractor and category in DISTRACTORS:
            body = body + " " + DISTRACTORS[category]
        # The hard-property is DERIVED from the final text with the same
        # label-free rule used by routing, so routing difficulty equals the
        # generated difficulty by construction (no generator/feature drift).
        features = derive_features(body)
        gold = {
            "category": category,
            "urgency": urgency,
            "refund_requested": refund,
            "due_date": due,
        }
        tasks.append(
            Task(
                task_id=f"tick-{index:04d}",
                split=split,
                text=body,
                gold=gold,
                multi_constraint=features.multi_topic,
            )
        )
    return tuple(tasks)


def _human_date(iso: str) -> str:
    year, month, day = iso.split("-")
    month_name = [name for name, num in MONTHS.items() if num == int(month)][0]
    return f"{month_name} {int(day)}, {year}"


def split_by(task: Task) -> str:
    return task.split


def digest(tasks: tuple[Task, ...]) -> str:
    payload = [
        {
            "task_id": t.task_id,
            "split": t.split,
            "text": t.text,
            "gold": dict(t.gold),
            "multi_constraint": t.multi_constraint,
        }
        for t in tasks
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# Oracle (exact-match, string equality) — used only for MEASUREMENT.

RESPONSE_KEYS = ("category", "urgency", "refund_requested", "due_date")


def parse_response_json(text: str) -> dict | None:
    """Extract the first JSON object from the response text, else None."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def score(task: Task, response_text: str) -> dict:
    """Exact-match oracle. Never used for routing. Returns:
    {"correct": bool, "field_errors": {...}} (field_errors only on failure)."""
    parsed = parse_response_json(response_text)
    if parsed is None:
        return {"correct": False, "field_errors": {"parse": "no valid JSON object"}}
    if any(key not in parsed for key in RESPONSE_KEYS):
        missing = [key for key in RESPONSE_KEYS if key not in parsed]
        return {"correct": False, "field_errors": {"missing": missing}}
    field_errors = {}
    for key in RESPONSE_KEYS:
        want = task.gold[key]
        got = parsed.get(key)
        if not isinstance(got, str) or got.strip() != want:
            field_errors[key] = {"want": want, "got": got}
    return {"correct": not field_errors, "field_errors": field_errors}


def user_prompt(task: Task) -> str:
    return task.text

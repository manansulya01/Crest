"""Multi-constraint invoice line-item extraction workload (Sprint 3).

Harder than the support-ticket workload: each task requires extracting 8 fields
including a line-items array, with a cross-field invariant
(sum(line_items.amount) + tax_amount == total_amount). Failures are detectable
by deterministic validation (no model judge).

Synthetic, documented — NOT real customer traffic. Gold labels are used only by
the oracle; routing features are derived from task text alone.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

SEED = 20261027

VENDORS = ("Acme Corp", "Globex Inc", "Initech LLC", "Umbrella Co", "Soylent Ltd")
CURRENCIES = ("USD", "EUR", "GBP")
ITEM_DESCRIPTIONS = (
    "Widget A", "Widget B", "Service hours", "Consulting", "License fee",
    "Support plan", "Hardware kit", "Data storage",
)

SPLIT_SIZES = {"calibration": 120, "pilot": 10, "heldout": 100}

PROMPT_SYSTEM = (
    "You extract fields from invoices. Reply ONLY with a JSON object of this "
    "schema and nothing else:\n"
    '{"vendor":..., "invoice_number":..., "invoice_date":..., "due_date":..., '
    '"currency":..., "total_amount":..., "line_items":[{...}], "tax_amount":...}\n'
    "vendor: exact vendor name from the invoice.\n"
    "invoice_number: exact invoice id (e.g. INV-0042).\n"
    "invoice_date: YYYY-MM-DD.\n"
    "due_date: YYYY-MM-DD or \"none\".\n"
    "currency: ISO code (USD/EUR/GBP).\n"
    "total_amount: total as string with two decimals.\n"
    "line_items: array of {description, quantity, unit_price, amount}; "
    "amount = quantity * unit_price, two decimals.\n"
    "tax_amount: tax as string with two decimals.\n"
    "Invariant: sum of line_items[].amount + tax_amount == total_amount."
)

RESPONSE_KEYS = ("vendor", "invoice_number", "invoice_date", "due_date",
                  "currency", "total_amount", "line_items", "tax_amount")


@dataclass(frozen=True)
class Task:
    task_id: str
    split: str
    text: str
    gold: Mapping
    multi_constraint: bool


def _rng(seed, index):
    import random
    return random.Random((seed * 7919 + index * 104729) & 0xFFFFFFFF)


def _money(rng, lo=10, hi=500) -> str:
    val = rng.uniform(lo, hi)
    return f"{val:.2f}"


def _iso_date(rng) -> str:
    y, m, d = 2026, rng.randint(1, 12), rng.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


from dataclasses import dataclass

@dataclass
class RoutingFeatures:
    multi_topic: bool

def derive_features(text: str) -> RoutingFeatures:
    multi = text.count(" - ") >= 2 or "tax" in text.lower()
    return RoutingFeatures(multi_topic=multi)


def derive_features(text: str):
    # Label-free: multi_constraint if the text mentions 2+ line items or a tax line.
    multi = text.count(" - ") >= 2 or "tax" in text.lower()
    return {"multi_constraint": multi, "has_tax": "tax" in text.lower(),
            "item_count": text.count(" - ")}


def generate_tasks(seed: int = SEED) -> tuple:
    tasks = []
    total = sum(SPLIT_SIZES.values())
    for index in range(total):
        rng = _rng(seed, index)
        if index < SPLIT_SIZES["calibration"]:
            split = "calibration"
        elif index < SPLIT_SIZES["calibration"] + SPLIT_SIZES["pilot"]:
            split = "pilot"
        else:
            split = "heldout"

        vendor = VENDORS[rng.randrange(len(VENDORS))]
        currency = CURRENCIES[rng.randrange(len(CURRENCIES))]
        inv_num = f"INV-{rng.randint(1000, 9999)}"
        inv_date = _iso_date(rng)
        has_due = rng.random() < 0.7
        due_date = _iso_date(rng) if has_due else "none"

        n_items = rng.randint(1, 4)
        items = []
        subtotal = Decimal("0")
        for _ in range(n_items):
            desc = ITEM_DESCRIPTIONS[rng.randrange(len(ITEM_DESCRIPTIONS))]
            qty = rng.randint(1, 5)
            unit = Decimal(f"{rng.uniform(5, 50):.2f}")
            amount = (Decimal(qty) * unit).quantize(Decimal("0.01"))
            subtotal += amount
            items.append({
                "description": desc,
                "quantity": qty,
                "unit_price": str(unit),
                "amount": str(amount),
            })

        tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        total_amt = (subtotal + tax).quantize(Decimal("0.01"))

        multi = n_items >= 2

        lines_text = "\n".join(
            f"  - {it['description']}: qty {it['quantity']} x {it['unit_price']} = {it['amount']}"
            for it in items
        )
        text = (
            f"Invoice from {vendor}. Invoice number: {inv_num}. "
            f"Date: {inv_date}. Due: {due_date if has_due else 'no due date'}. "
            f"Currency: {currency}.\n"
            f"Line items:\n{lines_text}\n"
            f"Tax (10%): {tax}. Total: {total_amt}."
        )

        gold = {
            "vendor": vendor,
            "invoice_number": inv_num,
            "invoice_date": inv_date,
            "due_date": due_date,
            "currency": currency,
            "total_amount": str(total_amt),
            "line_items": items,
            "tax_amount": str(tax),
        }

        tasks.append(Task(
            task_id=f"inv-{index:04d}",
            split=split,
            text=text,
            gold=gold,
            multi_constraint=multi,
        ))
    return tuple(tasks)


def digest(tasks):
    payload = [{"task_id": t.task_id, "split": t.split, "text": t.text,
                "gold": dict(t.gold), "multi": t.multi_constraint} for t in tasks]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def parse_response_json(text):
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _check_invariant(parsed) -> bool:
    try:
        items = parsed.get("line_items", [])
        if not isinstance(items, list):
            return False
        s = Decimal("0")
        for it in items:
            if not isinstance(it, dict):
                return False
            if not all(k in it for k in ("description", "quantity", "unit_price", "amount")):
                return False
            s += Decimal(str(it["amount"]))
        tax = Decimal(str(parsed.get("tax_amount")))
        total = Decimal(str(parsed.get("total_amount")))
        return (s + tax).quantize(Decimal("0.01")) == total.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return False


def score(task, response_text) -> dict:
    parsed = parse_response_json(response_text)
    if parsed is None:
        return {"correct": False, "field_errors": {"parse": "no valid JSON"}}
    missing = [k for k in RESPONSE_KEYS if k not in parsed]
    if missing:
        return {"correct": False, "field_errors": {"missing": missing}}
    # Exact match on scalar fields.
    errors = {}
    for key in ("vendor", "invoice_number", "invoice_date", "due_date",
                "currency", "total_amount", "tax_amount"):
        if str(parsed.get(key, "")).strip() != str(task.gold[key]).strip():
            errors[key] = {"want": task.gold[key], "got": parsed.get(key)}
    # Line items exact match.
    gold_items = task.gold["line_items"]
    got_items = parsed.get("line_items")
    if not isinstance(got_items, list) or len(got_items) != len(gold_items):
        errors["line_items"] = {"want": len(gold_items), "got": len(got_items) if isinstance(got_items, list) else got_items}
    else:
        for i, (g, got) in enumerate(zip(gold_items, got_items)):
            if not isinstance(got, dict):
                errors[f"line_items[{i}]"] = {"want": g, "got": got}
                continue
            for k in ("description", "quantity", "unit_price", "amount"):
                if str(got.get(k, "")).strip() != str(g[k]).strip():
                    errors[f"line_items[{i}].{k}"] = {"want": g[k], "got": got.get(k)}
    if errors:
        return {"correct": False, "field_errors": errors}
    # Cross-field invariant.
    if not _check_invariant(parsed):
        return {"correct": False, "field_errors": {"invariant": "sum+tax != total"}}
    return {"correct": True, "field_errors": {}}


def verify(task, response_text) -> bool:
    parsed = parse_response_json(response_text)
    if parsed is None:
        return False
    if any(k not in parsed for k in RESPONSE_KEYS):
        return False
    return _check_invariant(parsed)


def user_prompt(task):
    return task.text

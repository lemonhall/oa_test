from __future__ import annotations

import json
from typing import Any


def parse_payload_json(req_row) -> dict[str, Any] | None:
    if "payload_json" not in req_row.keys() or req_row["payload_json"] is None:
        return None
    try:
        obj = json.loads(str(req_row["payload_json"]))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def step_condition_passes(step_row, request_payload: dict[str, Any] | None, *, creator_dept: str | None) -> bool:
    kind = None if step_row["condition_kind"] is None else str(step_row["condition_kind"]).strip()
    value = None if step_row["condition_value"] is None else str(step_row["condition_value"]).strip()
    if not kind:
        return True
    if kind == "min_amount":
        if not request_payload:
            return False
        try:
            amount = float(request_payload.get("amount"))
            threshold = float(value or "0")
        except Exception:
            return False
        return amount >= threshold
    if kind == "max_amount":
        if not request_payload:
            return False
        try:
            amount = float(request_payload.get("amount"))
            threshold = float(value or "0")
        except Exception:
            return False
        return amount <= threshold
    if kind == "min_days":
        if not request_payload:
            return False
        try:
            days = int(request_payload.get("days"))
            threshold = int(value or "0")
        except Exception:
            return False
        return days >= threshold
    if kind == "dept_in":
        if not creator_dept:
            return False
        allowed = []
        for part in (value or "").replace(";", ",").split(","):
            part = part.strip()
            if part:
                allowed.append(part.lower())
        if not allowed:
            return False
        return creator_dept.strip().lower() in allowed
    if kind == "category_in":
        if not request_payload:
            return False
        category = str(request_payload.get("category", "")).strip()
        allowed = []
        for part in (value or "").replace(";", ",").split(","):
            part = part.strip()
            if part:
                allowed.append(part.lower())
        if not allowed:
            return False
        return category.lower() in allowed
    return True


def find_next_step(steps, *, current_order: int | None, request_payload: dict[str, Any] | None, creator_dept: str | None):
    if not steps:
        return None
    for s in steps:
        if current_order is not None and int(s["step_order"]) <= int(current_order):
            continue
        if step_condition_passes(s, request_payload, creator_dept=creator_dept):
            return s
    return None


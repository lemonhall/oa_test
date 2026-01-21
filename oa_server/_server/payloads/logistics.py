from __future__ import annotations

from typing import Any

from .common import is_hhmm, is_iso_date
from ..jsonutil import json_dumps


def try_build(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any],
) -> tuple[bool, str, str, str | None]:
    if request_type == "meeting_room":
        room = str(payload.get("room", "")).strip()
        date = str(payload.get("date", "")).strip()
        start_time = str(payload.get("start_time", "")).strip()
        end_time = str(payload.get("end_time", "")).strip()
        subject = str(payload.get("subject", "")).strip()
        if not room or not date or not start_time or not end_time or not subject:
            raise ValueError("invalid_payload")
        if not is_iso_date(date) or not is_hhmm(start_time) or not is_hhmm(end_time):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["room"] = room
        payload["date"] = date
        payload["start_time"] = start_time
        payload["end_time"] = end_time
        payload["subject"] = subject
        if not title:
            title = f"会议室预定：{room}"
        if not body:
            body = f"日期：{date}\n时间：{start_time}~{end_time}\n主题：{subject}"
        return True, title, body, json_dumps(payload)

    if request_type == "car":
        date = str(payload.get("date", "")).strip()
        start_time = str(payload.get("start_time", "")).strip()
        end_time = str(payload.get("end_time", "")).strip()
        from_loc = str(payload.get("from", "")).strip()
        to_loc = str(payload.get("to", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not date or not start_time or not end_time or not from_loc or not to_loc or not reason:
            raise ValueError("invalid_payload")
        if not is_iso_date(date) or not is_hhmm(start_time) or not is_hhmm(end_time):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["date"] = date
        payload["start_time"] = start_time
        payload["end_time"] = end_time
        payload["from"] = from_loc
        payload["to"] = to_loc
        payload["reason"] = reason
        if not title:
            title = "用车："
        if not body:
            body = f"日期：{date}\n时间：{start_time}~{end_time}\n路线：{from_loc} → {to_loc}\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "supplies":
        items = payload.get("items")
        reason = str(payload.get("reason", "")).strip()
        if not isinstance(items, list) or not items or not reason:
            raise ValueError("invalid_payload")
        normalized_items: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                raise ValueError("invalid_payload")
            name = str(it.get("name", "")).strip()
            try:
                qty = int(it.get("qty", 0))
            except Exception:
                qty = 0
            if not name or qty <= 0:
                raise ValueError("invalid_payload")
            normalized_items.append({"name": name, "qty": qty})
        payload = dict(payload)
        payload["items"] = normalized_items
        payload["reason"] = reason
        if not title:
            title = f"物品领用：{normalized_items[0]['name']}"
        if not body:
            lines = [f"- {x['name']} × {x['qty']}" for x in normalized_items]
            body = "领用明细：\n" + "\n".join(lines) + f"\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


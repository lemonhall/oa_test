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
    if request_type == "leave":
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        days_raw = payload.get("days", None)
        try:
            days = int(days_raw)
        except Exception:
            days = 0
        if not start_date or not end_date or not reason or days <= 0:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date) or not is_iso_date(end_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"请假：{start_date}~{end_date}（{days}天）"
        if not body:
            body = f"原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "overtime":
        date = str(payload.get("date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        hours_raw = payload.get("hours", None)
        try:
            hours = float(hours_raw)
        except Exception:
            hours = 0.0
        if not date or not reason or hours <= 0:
            raise ValueError("invalid_payload")
        if not is_iso_date(date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["date"] = date
        payload["reason"] = reason
        payload["hours"] = hours
        if not title:
            title = f"加班：{date}（{hours:g}小时）"
        if not body:
            body = f"原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "attendance_correction":
        date = str(payload.get("date", "")).strip()
        kind = str(payload.get("kind", "")).strip()
        tm = str(payload.get("time", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if kind in {"上班", "签到"}:
            kind = "in"
        if kind in {"下班", "签退"}:
            kind = "out"
        if not date or not tm or not reason or kind not in {"in", "out"}:
            raise ValueError("invalid_payload")
        if not is_iso_date(date) or not is_hhmm(tm):
            raise ValueError("invalid_payload")
        kind_text = "上班" if kind == "in" else "下班"
        if not title:
            title = f"补卡：{date} {tm}（{kind_text}）"
        if not body:
            body = f"原因：{reason}"
        payload = dict(payload)
        payload["date"] = date
        payload["time"] = tm
        payload["kind"] = kind
        payload["reason"] = reason
        return True, title, body, json_dumps(payload)

    if request_type == "business_trip":
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        destination = str(payload.get("destination", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        if not start_date or not end_date or not destination or not purpose:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date) or not is_iso_date(end_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"出差：{destination} {start_date}~{end_date}"
        if not body:
            body = f"事由：{purpose}"
        payload = dict(payload)
        payload["start_date"] = start_date
        payload["end_date"] = end_date
        payload["destination"] = destination
        payload["purpose"] = purpose
        return True, title, body, json_dumps(payload)

    if request_type == "outing":
        date = str(payload.get("date", "")).strip()
        start_time = str(payload.get("start_time", "")).strip()
        end_time = str(payload.get("end_time", "")).strip()
        destination = str(payload.get("destination", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not date or not start_time or not end_time or not destination or not reason:
            raise ValueError("invalid_payload")
        if not is_iso_date(date) or not is_hhmm(start_time) or not is_hhmm(end_time):
            raise ValueError("invalid_payload")
        if not title:
            title = f"外出：{destination} {date} {start_time}~{end_time}"
        if not body:
            body = f"原因：{reason}"
        payload = dict(payload)
        payload["date"] = date
        payload["start_time"] = start_time
        payload["end_time"] = end_time
        payload["destination"] = destination
        payload["reason"] = reason
        return True, title, body, json_dumps(payload)

    if request_type == "travel_expense":
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not start_date or not end_date or amount <= 0:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date) or not is_iso_date(end_date):
            raise ValueError("invalid_payload")
        if not title:
            title = f"差旅报销：{start_date}~{end_date} {amount:g}元"
        if not body:
            body = f"说明：{reason}" if reason else "说明：差旅报销"
        payload = dict(payload)
        payload["start_date"] = start_date
        payload["end_date"] = end_date
        payload["amount"] = amount
        payload["reason"] = reason
        return True, title, body, json_dumps(payload)

    return False, title, body, None


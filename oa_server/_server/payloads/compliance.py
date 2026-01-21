from __future__ import annotations

from typing import Any

from .common import is_iso_date
from ..jsonutil import json_dumps


def try_build(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any],
) -> tuple[bool, str, str, str | None]:
    if request_type == "policy_announcement":
        subject = str(payload.get("subject", "")).strip()
        content = str(payload.get("content", "")).strip()
        effective_date = str(payload.get("effective_date", "")).strip()
        if not subject or not content:
            raise ValueError("invalid_payload")
        if effective_date and not is_iso_date(effective_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["subject"] = subject
        payload["content"] = content
        payload["effective_date"] = effective_date
        if not title:
            title = f"公告：{subject}"
        if not body:
            body = content + (f"\n生效日期：{effective_date}" if effective_date else "")
        return True, title, body, json_dumps(payload)

    if request_type == "read_ack":
        subject = str(payload.get("subject", "")).strip()
        content = str(payload.get("content", "")).strip()
        due_date = str(payload.get("due_date", "")).strip()
        if not subject or not content:
            raise ValueError("invalid_payload")
        if due_date and not is_iso_date(due_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["subject"] = subject
        payload["content"] = content
        payload["due_date"] = due_date
        if not title:
            title = f"阅读确认：{subject}"
        if not body:
            body = content + (f"\n截止日期：{due_date}" if due_date else "")
        return True, title, body, json_dumps(payload)

    return False, title, body, None


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
    if request_type == "contract":
        name = str(payload.get("name", "")).strip()
        party = str(payload.get("party", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not name or not party or amount <= 0 or not start_date or not end_date:
            raise ValueError("invalid_payload")
        if not is_iso_date(start_date) or not is_iso_date(end_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["name"] = name
        payload["party"] = party
        payload["amount"] = amount
        payload["start_date"] = start_date
        payload["end_date"] = end_date
        payload["summary"] = summary
        if not title:
            title = f"合同：{name}"
        if not body:
            body = f"对方：{party}\n金额：{amount:g}元\n期限：{start_date}~{end_date}"
            if summary:
                body += f"\n摘要：{summary}"
        return True, title, body, json_dumps(payload)

    if request_type == "legal_review":
        subject = str(payload.get("subject", "")).strip()
        risk_level = str(payload.get("risk_level", "")).strip().lower()
        notes = str(payload.get("notes", "")).strip()
        if risk_level in {"low", "medium", "high"}:
            pass
        elif risk_level in {"低", "low"}:
            risk_level = "low"
        elif risk_level in {"中", "medium"}:
            risk_level = "medium"
        elif risk_level in {"高", "high"}:
            risk_level = "high"
        else:
            raise ValueError("invalid_payload")
        if not subject:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["subject"] = subject
        payload["risk_level"] = risk_level
        payload["notes"] = notes
        if not title:
            title = f"法务审查：{subject}"
        if not body:
            rl = "低" if risk_level == "low" else "中" if risk_level == "medium" else "高"
            body = f"风险等级：{rl}"
            if notes:
                body += f"\n备注：{notes}"
        return True, title, body, json_dumps(payload)

    if request_type == "seal":
        document = str(payload.get("document", "")).strip()
        seal_type = str(payload.get("seal_type", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        needed_date = str(payload.get("needed_date", "")).strip()
        if not document or not seal_type or not purpose or not needed_date:
            raise ValueError("invalid_payload")
        if not is_iso_date(needed_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["document"] = document
        payload["seal_type"] = seal_type
        payload["purpose"] = purpose
        payload["needed_date"] = needed_date
        if not title:
            title = f"用章：{document}"
        if not body:
            body = f"类型：{seal_type}\n用途：{purpose}\n需要日期：{needed_date}"
        return True, title, body, json_dumps(payload)

    if request_type == "archive":
        document = str(payload.get("document", "")).strip()
        archive_type = str(payload.get("archive_type", "")).strip()
        retention_years_raw = payload.get("retention_years", None)
        try:
            retention_years = int(retention_years_raw)
        except Exception:
            retention_years = 0
        if not document or not archive_type or retention_years <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["document"] = document
        payload["archive_type"] = archive_type
        payload["retention_years"] = retention_years
        if not title:
            title = f"归档：{document}"
        if not body:
            body = f"类型：{archive_type}\n保管：{retention_years}年"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


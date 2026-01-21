from __future__ import annotations

from typing import Any

from ..jsonutil import json_dumps


def try_build(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any],
) -> tuple[bool, str, str, str | None]:
    if request_type == "expense":
        category = str(payload.get("category", "")).strip() or "报销"
        reason = str(payload.get("reason", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if amount <= 0:
            raise ValueError("invalid_payload")
        if not title:
            title = f"报销：{category} {amount:g}元"
        if not body:
            body = reason or f"类别：{category}"
        return True, title, body, json_dumps(payload)

    if request_type == "loan":
        amount_raw = payload.get("amount", None)
        reason = str(payload.get("reason", "")).strip()
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if amount <= 0 or not reason:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["amount"] = amount
        payload["reason"] = reason
        if not title:
            title = f"借款：{amount:g}元"
        if not body:
            body = f"用途：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "payment":
        payee = str(payload.get("payee", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not payee or not purpose or amount <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["payee"] = payee
        payload["purpose"] = purpose
        payload["amount"] = amount
        if not title:
            title = f"付款：{payee} {amount:g}元"
        if not body:
            body = f"用途：{purpose}"
        return True, title, body, json_dumps(payload)

    if request_type == "budget":
        dept = str(payload.get("dept", "")).strip()
        period = str(payload.get("period", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not dept or not period or not purpose or amount <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["dept"] = dept
        payload["period"] = period
        payload["purpose"] = purpose
        payload["amount"] = amount
        if not title:
            title = f"预算：{dept} {period} {amount:g}元"
        if not body:
            body = f"用途：{purpose}"
        return True, title, body, json_dumps(payload)

    if request_type == "invoice":
        invoice_title = str(payload.get("title", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not invoice_title or not purpose or amount <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["title"] = invoice_title
        payload["purpose"] = purpose
        payload["amount"] = amount
        if not title:
            title = f"开票：{invoice_title} {amount:g}元"
        if not body:
            body = f"用途：{purpose}"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


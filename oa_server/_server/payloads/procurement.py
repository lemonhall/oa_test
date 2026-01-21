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
    if request_type == "purchase":
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("invalid_payload")
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise ValueError("invalid_payload")

        total = 0.0
        normalized_items: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                raise ValueError("invalid_payload")
            name = str(it.get("name", "")).strip()
            try:
                qty = int(it.get("qty", 0))
            except Exception:
                qty = 0
            try:
                unit_price = float(it.get("unit_price", 0))
            except Exception:
                unit_price = 0.0
            if not name or qty <= 0 or unit_price <= 0:
                raise ValueError("invalid_payload")
            line_total = qty * unit_price
            total += line_total
            normalized_items.append({"name": name, "qty": qty, "unit_price": unit_price, "line_total": line_total})

        if total <= 0:
            raise ValueError("invalid_payload")

        payload = dict(payload)
        payload["items"] = normalized_items
        payload["amount"] = float(payload.get("amount", total)) if payload.get("amount") is not None else total
        payload["amount"] = total

        if not title:
            first = normalized_items[0]["name"]
            more = f"等{len(normalized_items)}项" if len(normalized_items) > 1 else ""
            title = f"采购：{first}{more} {total:g}元"
        if not body:
            body = f"原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "purchase_plus":
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("invalid_payload")
        reason = str(payload.get("reason", "")).strip()
        vendor = str(payload.get("vendor", "")).strip()
        delivery_date = str(payload.get("delivery_date", "")).strip()
        if not reason or not vendor or not delivery_date:
            raise ValueError("invalid_payload")
        if not is_iso_date(delivery_date):
            raise ValueError("invalid_payload")

        total = 0.0
        normalized_items: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                raise ValueError("invalid_payload")
            name = str(it.get("name", "")).strip()
            try:
                qty = int(it.get("qty", 0))
            except Exception:
                qty = 0
            try:
                unit_price = float(it.get("unit_price", 0))
            except Exception:
                unit_price = 0.0
            if not name or qty <= 0 or unit_price <= 0:
                raise ValueError("invalid_payload")
            line_total = qty * unit_price
            total += line_total
            normalized_items.append({"name": name, "qty": qty, "unit_price": unit_price, "line_total": line_total})

        if total <= 0:
            raise ValueError("invalid_payload")

        payload = dict(payload)
        payload["items"] = normalized_items
        payload["amount"] = total
        payload["reason"] = reason
        payload["vendor"] = vendor
        payload["delivery_date"] = delivery_date

        if not title:
            first = normalized_items[0]["name"]
            more = f"等{len(normalized_items)}项" if len(normalized_items) > 1 else ""
            title = f"采购（增强）：{first}{more} {total:g}元"
        if not body:
            body = f"供应商：{vendor}\n交付日期：{delivery_date}\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "quote_compare":
        subject = str(payload.get("subject", "")).strip()
        vendors = payload.get("vendors", None)
        recommendation = str(payload.get("recommendation", "")).strip()
        if not subject or not isinstance(vendors, list) or len(vendors) < 2:
            raise ValueError("invalid_payload")
        vendor_names: list[str] = []
        for v in vendors:
            s = str(v).strip()
            if s:
                vendor_names.append(s)
        if len(vendor_names) < 2:
            raise ValueError("invalid_payload")
        if not recommendation:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["subject"] = subject
        payload["vendors"] = vendor_names
        payload["recommendation"] = recommendation
        if not title:
            title = f"比价：{subject}"
        if not body:
            body = f"供应商：{', '.join(vendor_names)}\n推荐：{recommendation}"
        return True, title, body, json_dumps(payload)

    if request_type == "acceptance":
        purchase_ref = str(payload.get("purchase_ref", "")).strip()
        acceptance_date = str(payload.get("acceptance_date", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        if not purchase_ref or not acceptance_date or not summary:
            raise ValueError("invalid_payload")
        if not is_iso_date(acceptance_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["purchase_ref"] = purchase_ref
        payload["acceptance_date"] = acceptance_date
        payload["summary"] = summary
        if not title:
            title = f"验收：{purchase_ref}"
        if not body:
            body = f"验收日期：{acceptance_date}\n说明：{summary}"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


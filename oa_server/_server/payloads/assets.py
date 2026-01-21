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
    if request_type == "fixed_asset_accounting":
        asset_name = str(payload.get("asset_name", "")).strip()
        acquired_date = str(payload.get("acquired_date", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not asset_name or amount <= 0 or not acquired_date:
            raise ValueError("invalid_payload")
        if not is_iso_date(acquired_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["asset_name"] = asset_name
        payload["amount"] = amount
        payload["acquired_date"] = acquired_date
        if not title:
            title = f"固定资产入账：{asset_name} {amount:g}元"
        if not body:
            body = f"购置日期：{acquired_date}"
        return True, title, body, json_dumps(payload)

    if request_type in {"inventory_in", "inventory_out"}:
        warehouse = str(payload.get("warehouse", "")).strip()
        date = str(payload.get("date", "")).strip()
        items = payload.get("items")
        reason = str(payload.get("reason", "")).strip()
        if not warehouse or not date or not isinstance(items, list) or not items:
            raise ValueError("invalid_payload")
        if not is_iso_date(date):
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
        if request_type == "inventory_out" and not reason:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["warehouse"] = warehouse
        payload["date"] = date
        payload["items"] = normalized_items
        payload["reason"] = reason
        kind_text = "入库" if request_type == "inventory_in" else "出库"
        if not title:
            title = f"{kind_text}：{warehouse} {date}（{len(normalized_items)}项）"
        if not body:
            lines = [f"- {x['name']} × {x['qty']}" for x in normalized_items]
            body = f"{kind_text}明细：\n" + "\n".join(lines)
            if reason:
                body += f"\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "device_claim":
        item = str(payload.get("item", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        qty_raw = payload.get("qty", None)
        try:
            qty = int(qty_raw)
        except Exception:
            qty = 0
        if not item or qty <= 0 or not reason:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["item"] = item
        payload["qty"] = qty
        payload["reason"] = reason
        if not title:
            title = f"申领：{item}×{qty}"
        if not body:
            body = f"原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "asset_transfer":
        asset = str(payload.get("asset", "")).strip()
        from_user = str(payload.get("from_user", "")).strip()
        to_user = str(payload.get("to_user", "")).strip()
        date = str(payload.get("date", "")).strip()
        if not asset or not from_user or not to_user or not date:
            raise ValueError("invalid_payload")
        if not is_iso_date(date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["asset"] = asset
        payload["from_user"] = from_user
        payload["to_user"] = to_user
        payload["date"] = date
        if not title:
            title = f"调拨：{asset} {from_user}→{to_user}"
        if not body:
            body = f"日期：{date}"
        return True, title, body, json_dumps(payload)

    if request_type == "asset_maintenance":
        asset = str(payload.get("asset", "")).strip()
        issue = str(payload.get("issue", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if not asset or not issue or amount < 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["asset"] = asset
        payload["issue"] = issue
        payload["amount"] = amount
        if not title:
            title = f"维修：{asset}"
        if not body:
            body = f"问题：{issue}" + (f"\n预计费用：{amount:g}元" if amount else "")
        return True, title, body, json_dumps(payload)

    if request_type == "asset_scrap":
        asset = str(payload.get("asset", "")).strip()
        scrap_date = str(payload.get("scrap_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw) if amount_raw is not None else 0.0
        except Exception:
            amount = 0.0
        if not asset or not scrap_date or not reason or amount < 0:
            raise ValueError("invalid_payload")
        if not is_iso_date(scrap_date):
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["asset"] = asset
        payload["scrap_date"] = scrap_date
        payload["reason"] = reason
        payload["amount"] = amount
        if not title:
            title = f"报废：{asset}"
        if not body:
            body = f"报废日期：{scrap_date}\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


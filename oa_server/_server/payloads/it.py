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
    if request_type == "account_open":
        system = str(payload.get("system", "")).strip()
        account = str(payload.get("account", "")).strip()
        dept = str(payload.get("dept", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not system or not account or not dept or not reason:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["system"] = system
        payload["account"] = account
        payload["dept"] = dept
        payload["reason"] = reason
        if not title:
            title = f"账号开通：{system}"
        if not body:
            body = f"账号：{account}\n部门：{dept}\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "permission":
        system = str(payload.get("system", "")).strip()
        perm = str(payload.get("permission", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        duration_raw = payload.get("duration_days", None)
        try:
            duration_days = int(duration_raw)
        except Exception:
            duration_days = 0
        if not system or not perm or not reason or duration_days <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["system"] = system
        payload["permission"] = perm
        payload["duration_days"] = duration_days
        payload["reason"] = reason
        if not title:
            title = f"权限申请：{system}"
        if not body:
            body = f"权限：{perm}\n期限：{duration_days}天\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "vpn_email":
        kind = str(payload.get("kind", "")).strip().lower()
        account = str(payload.get("account", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if kind in {"vpn", "VPN"}:
            kind = "vpn"
        elif kind in {"email", "mail", "邮箱"}:
            kind = "email"
        else:
            raise ValueError("invalid_payload")
        if not account or not reason:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["kind"] = kind
        payload["account"] = account
        payload["reason"] = reason
        kind_text = "VPN" if kind == "vpn" else "邮箱"
        if not title:
            title = f"开通：{kind_text}"
        if not body:
            body = f"账号：{account}\n原因：{reason}"
        return True, title, body, json_dumps(payload)

    if request_type == "it_device":
        item = str(payload.get("item", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        qty_raw = payload.get("qty", None)
        try:
            qty = int(qty_raw)
        except Exception:
            qty = 0
        if not item or not reason or qty <= 0:
            raise ValueError("invalid_payload")
        payload = dict(payload)
        payload["item"] = item
        payload["qty"] = qty
        payload["reason"] = reason
        if not title:
            title = f"设备申请：{item}×{qty}"
        if not body:
            body = f"原因：{reason}"
        return True, title, body, json_dumps(payload)

    return False, title, body, None


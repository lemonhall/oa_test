from __future__ import annotations

from http import HTTPStatus

from .. import db
from .jsonutil import read_json


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/admin/workflows":
        handler._require_permission("workflows:manage")
        payload = read_json(handler) or {}
        workflow_key = str(payload.get("workflow_key", "")).strip()
        request_type = str(payload.get("request_type", "")).strip()
        name = str(payload.get("name", "")).strip()
        category = str(payload.get("category", "")).strip() or "General"
        scope_kind = str(payload.get("scope_kind", "global")).strip() or "global"
        scope_value = payload.get("scope_value", None)
        scope_value_s = None if scope_value in (None, "") else str(scope_value).strip()
        enabled = bool(payload.get("enabled", True))
        is_default = bool(payload.get("is_default", False))
        steps = payload.get("steps", None)
        if not workflow_key or not request_type or not name:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        if scope_kind not in {"global", "dept"}:
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_scope")
            return True
        if scope_kind == "dept" and not scope_value_s:
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_scope")
            return True
        if steps is not None and not isinstance(steps, list):
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_steps")
            return True
        with db.connect(handler.server.db_path) as conn:
            db.upsert_workflow_variant(
                conn,
                workflow_key=workflow_key,
                request_type=request_type,
                name=name,
                category=category,
                scope_kind=scope_kind,
                scope_value=scope_value_s,
                enabled=enabled,
                is_default=is_default,
            )
            if steps is not None:
                db.replace_workflow_variant_steps(conn, workflow_key, steps)
        handler._send_json(HTTPStatus.CREATED, {"ok": True})
        return True

    if path == "/api/admin/roles":
        handler._require_permission("rbac:manage")
        payload = read_json(handler) or {}
        role_name = str(payload.get("role", "")).strip()
        permissions = payload.get("permissions", None)
        if not role_name or not isinstance(permissions, list):
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        perms: list[str] = []
        for p in permissions:
            if p in (None, ""):
                continue
            perms.append(str(p).strip())
        with db.connect(handler.server.db_path) as conn:
            db.upsert_role(conn, role_name)
            db.replace_role_permissions(conn, role_name, perms)
        handler._send_json(HTTPStatus.CREATED, {"ok": True})
        return True

    if path == "/api/admin/departments":
        handler._require_permission("org:manage")
        payload = read_json(handler) or {}
        name = str(payload.get("name", "")).strip()
        parent_id = payload.get("parent_id", None)
        if not name:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        parent_id_i = None if parent_id in (None, "") else int(parent_id)
        with db.connect(handler.server.db_path) as conn:
            if parent_id_i is not None and not db.get_department(conn, parent_id_i):
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_parent_id")
                return True
            try:
                dept_id = db.create_department(conn, name=name, parent_id=parent_id_i)
            except Exception:
                handler._send_error(HTTPStatus.CONFLICT, "conflict")
                return True
        handler._send_json(HTTPStatus.CREATED, {"id": int(dept_id)})
        return True

    if path == "/api/admin/workflows/delete":
        handler._require_permission("workflows:manage")
        payload = read_json(handler) or {}
        workflow_key = str(payload.get("workflow_key", "")).strip()
        if not workflow_key:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        with db.connect(handler.server.db_path) as conn:
            db.delete_workflow_variant(conn, workflow_key)
        handler._send_empty(HTTPStatus.NO_CONTENT)
        return True

    return False


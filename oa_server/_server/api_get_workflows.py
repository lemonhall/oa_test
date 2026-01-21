from __future__ import annotations

from http import HTTPStatus

from .. import db


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/workflows":
        user = handler._require_user()
        with db.connect(handler.server.db_path) as conn:
            rows = db.list_available_workflow_variants(conn, dept=user.dept)
        handler._send_json(
            HTTPStatus.OK,
            {
                "items": [
                    {
                        "key": str(r["workflow_key"]),
                        "request_type": str(r["request_type"]),
                        "name": str(r["name"]),
                        "category": str(r["category"]),
                        "scope_kind": str(r["scope_kind"]),
                        "scope_value": None if r["scope_value"] is None else str(r["scope_value"]),
                        "is_default": bool(int(r["is_default"])),
                    }
                    for r in rows
                ]
            },
        )
        return True

    if path == "/api/admin/workflows":
        handler._require_permission("workflows:manage")
        with db.connect(handler.server.db_path) as conn:
            rows = db.list_workflow_variants_admin(conn)
        handler._send_json(
            HTTPStatus.OK,
            {
                "items": [
                    {
                        "key": str(r["workflow_key"]),
                        "request_type": str(r["request_type"]),
                        "name": str(r["name"]),
                        "category": str(r["category"]),
                        "scope_kind": str(r["scope_kind"]),
                        "scope_value": None if r["scope_value"] is None else str(r["scope_value"]),
                        "enabled": bool(int(r["enabled"])),
                        "is_default": bool(int(r["is_default"])),
                    }
                    for r in rows
                ]
            },
        )
        return True

    if path.startswith("/api/admin/workflows/"):
        handler._require_permission("workflows:manage")
        workflow_key = path.split("/", 4)[-1]
        with db.connect(handler.server.db_path) as conn:
            wf = db.get_workflow_variant(conn, workflow_key)
            if not wf:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            steps = db.list_workflow_variant_steps(conn, workflow_key)
        handler._send_json(
            HTTPStatus.OK,
            {
                "workflow": {
                    "key": str(wf["workflow_key"]),
                    "request_type": str(wf["request_type"]),
                    "name": str(wf["name"]),
                    "category": str(wf["category"]),
                    "scope_kind": str(wf["scope_kind"]),
                    "scope_value": None if wf["scope_value"] is None else str(wf["scope_value"]),
                    "enabled": bool(int(wf["enabled"])),
                    "is_default": bool(int(wf["is_default"])),
                },
                "steps": [
                    {
                        "step_order": int(s["step_order"]),
                        "step_key": str(s["step_key"]),
                        "assignee_kind": str(s["assignee_kind"]),
                        "assignee_value": None if s["assignee_value"] is None else str(s["assignee_value"]),
                        "condition_kind": None if s["condition_kind"] is None else str(s["condition_kind"]),
                        "condition_value": None if s["condition_value"] is None else str(s["condition_value"]),
                    }
                    for s in steps
                ],
            },
        )
        return True

    return False


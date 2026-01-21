from __future__ import annotations

from http import HTTPStatus
from typing import Any

from .. import db


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/admin/roles":
        handler._require_permission("rbac:manage")
        with db.connect(handler.server.db_path) as conn:
            roles = db.list_roles(conn)
            items = [{"role": str(r["name"]), "permissions": db.list_role_permissions(conn, str(r["name"]))} for r in roles]
        handler._send_json(HTTPStatus.OK, {"items": items})
        return True

    if path == "/api/admin/departments":
        handler._require_permission("org:manage")
        with db.connect(handler.server.db_path) as conn:
            rows = db.list_departments(conn)
        handler._send_json(
            HTTPStatus.OK,
            {
                "items": [
                    {
                        "id": int(r["id"]),
                        "name": str(r["name"]),
                        "parent_id": None if r["parent_id"] is None else int(r["parent_id"]),
                    }
                    for r in rows
                ]
            },
        )
        return True

    if path == "/api/org/tree":
        handler._require_user()
        with db.connect(handler.server.db_path) as conn:
            rows = db.list_departments(conn)
        nodes: dict[int, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []
        for r in rows:
            did = int(r["id"])
            nodes[did] = {
                "id": did,
                "name": str(r["name"]),
                "children": [],
                "parent_id": None if r["parent_id"] is None else int(r["parent_id"]),
            }
        for n in nodes.values():
            pid = n["parent_id"]
            if pid is not None and pid in nodes:
                nodes[pid]["children"].append(n)
            else:
                roots.append(n)
        handler._send_json(HTTPStatus.OK, {"items": roots})
        return True

    return False


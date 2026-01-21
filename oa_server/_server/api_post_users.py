from __future__ import annotations

from http import HTTPStatus

from .. import db
from .ids import parse_user_id
from .jsonutil import read_json


def try_handle(handler, path: str, query: str) -> bool:
    if not path.startswith("/api/users/"):
        return False

    handler._require_permission("users:manage")
    user_id = parse_user_id(path, suffix="")
    payload = read_json(handler) or {}
    updates: dict[str, object] = {}
    if "dept" in payload:
        dept = payload.get("dept")
        updates["dept"] = None if dept is None else str(dept).strip()
    if "manager_id" in payload:
        manager_id = payload.get("manager_id")
        updates["manager_id"] = None if manager_id in (None, "") else int(manager_id)
    if "role" in payload:
        role = payload.get("role")
        updates["role"] = None if role in (None, "") else str(role).strip()
    if "dept_id" in payload:
        dept_id = payload.get("dept_id")
        updates["dept_id"] = None if dept_id in (None, "") else int(dept_id)
    if "position" in payload:
        position = payload.get("position")
        updates["position"] = None if position in (None, "") else str(position).strip()

    with db.connect(handler.server.db_path) as conn:
        if "manager_id" in updates and updates["manager_id"] is not None:
            mgr = db.get_user_by_id(conn, int(updates["manager_id"]))
            if not mgr:
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_manager_id")
                return True
        if "role" in updates:
            role_v = updates["role"]
            if role_v is None or not str(role_v).strip():
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_role")
                return True
            if not db.role_exists(conn, str(role_v)):
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_role")
                return True
        if "dept_id" in updates and updates["dept_id"] is not None:
            if not db.get_department(conn, int(updates["dept_id"])):
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_dept_id")
                return True
        db.update_user(conn, user_id, **updates)

    handler._send_empty(HTTPStatus.NO_CONTENT)
    return True


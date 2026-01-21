from __future__ import annotations

from http import HTTPStatus

from .. import db


def try_handle(handler, path: str, query: str) -> bool:
    if path != "/api/me":
        return False

    user = handler._require_user()
    with db.connect(handler.server.db_path) as conn:
        permissions = ["*"] if user.role == "admin" else db.list_role_permissions(conn, user.role)
    handler._send_json(
        HTTPStatus.OK,
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "dept": user.dept,
            "manager_id": user.manager_id,
            "permissions": permissions,
        },
    )
    return True


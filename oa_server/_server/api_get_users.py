from __future__ import annotations

from http import HTTPStatus

from .. import db
from .serializers import row_to_user


def try_handle(handler, path: str, query: str) -> bool:
    if path != "/api/users":
        return False
    handler._require_permission("users:manage")
    with db.connect(handler.server.db_path) as conn:
        rows = db.list_users(conn)
    handler._send_json(HTTPStatus.OK, {"items": [row_to_user(r) for r in rows]})
    return True


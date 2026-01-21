from __future__ import annotations

from http import HTTPStatus

from .. import db
from .serializers import row_to_notification


def try_handle(handler, path: str, query: str) -> bool:
    if path != "/api/notifications":
        return False
    user = handler._require_user()
    with db.connect(handler.server.db_path) as conn:
        rows = db.list_notifications(conn, user_id=user.id)
    handler._send_json(HTTPStatus.OK, {"items": [row_to_notification(r) for r in rows]})
    return True


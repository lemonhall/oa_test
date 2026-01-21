from __future__ import annotations

from http import HTTPStatus

from .. import db
from .ids import parse_notification_id


def try_handle(handler, path: str, query: str) -> bool:
    if not (path.startswith("/api/notifications/") and path.endswith("/read")):
        return False

    user = handler._require_user()
    notification_id = parse_notification_id(path, suffix="/read")
    with db.connect(handler.server.db_path) as conn:
        ok = db.mark_notification_read(conn, notification_id, user_id=user.id)
    if not ok:
        handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
        return True
    handler._send_empty(HTTPStatus.NO_CONTENT)
    return True


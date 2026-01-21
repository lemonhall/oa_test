from __future__ import annotations

from http import HTTPStatus

from .. import db
from .jsonutil import read_json


def try_handle(handler, path: str, query: str) -> bool:
    if path != "/api/me/delegation":
        return False

    user = handler._require_user()
    payload = read_json(handler) or {}
    delegate_user_id = payload.get("delegate_user_id", None)
    if delegate_user_id in (None, ""):
        with db.connect(handler.server.db_path) as conn:
            db.set_delegation(conn, user.id, delegate_user_id=None, active=False)
        handler._send_json(HTTPStatus.CREATED, {"ok": True})
        return True

    try:
        delegate_user_id_i = int(delegate_user_id)
    except Exception:
        handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_id")
        return True
    if delegate_user_id_i == user.id:
        handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_delegate")
        return True
    with db.connect(handler.server.db_path) as conn:
        if not db.get_user_by_id(conn, delegate_user_id_i):
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_delegate")
            return True
        db.set_delegation(conn, user.id, delegate_user_id=delegate_user_id_i, active=True)
    handler._send_json(HTTPStatus.CREATED, {"ok": True})
    return True


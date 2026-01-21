from __future__ import annotations

import time
from http import HTTPStatus

from .. import db
from ..auth import new_session_token, parse_cookie_header, verify_password
from .jsonutil import read_json
from .session import SESSION_COOKIE, SESSION_TTL_SECONDS, build_session_cookie


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/login":
        payload = read_json(handler) or {}
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if not username or not password:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_credentials")
            return True

        with db.connect(handler.server.db_path) as conn:
            user = db.get_user_by_username(conn, username)
            if not user or not verify_password(password, str(user["password_hash"])):
                handler._send_error(HTTPStatus.UNAUTHORIZED, "invalid_credentials")
                return True

            token = new_session_token()
            expires_at = int(time.time()) + SESSION_TTL_SECONDS
            db.create_session(conn, token, int(user["id"]), expires_at)

        cookie = build_session_cookie(token)
        handler._send_json(
            HTTPStatus.OK,
            {"id": int(user["id"]), "username": str(user["username"]), "role": str(user["role"])},
            headers={"Set-Cookie": cookie},
        )
        return True

    if path == "/api/logout":
        cookies = parse_cookie_header(handler.headers.get("Cookie"))
        token = cookies.get(SESSION_COOKIE)
        if token:
            with db.connect(handler.server.db_path) as conn:
                db.delete_session(conn, token)
        handler._send_empty(
            HTTPStatus.NO_CONTENT,
            headers={"Set-Cookie": build_session_cookie("", expires_immediately=True)},
        )
        return True

    return False


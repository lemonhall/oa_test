from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import db
from .auth import AuthenticatedUser, new_session_token, parse_cookie_header, verify_password


SESSION_COOKIE = "oa_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _read_json(handler: BaseHTTPRequestHandler) -> Any:
    length_s = handler.headers.get("Content-Length", "0")
    try:
        length = int(length_s)
    except ValueError:
        length = 0
    raw = handler.rfile.read(length) if length > 0 else b""
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


class OAHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, db_path: Path, frontend_dir: Path):
        super().__init__(server_address, RequestHandlerClass)
        self.db_path = db_path
        self.frontend_dir = frontend_dir


class Handler(BaseHTTPRequestHandler):
    server: OAHTTPServer  # type: ignore[assignment]

    def _send_json(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def _get_current_user(self) -> AuthenticatedUser | None:
        cookies = parse_cookie_header(self.headers.get("Cookie"))
        token = cookies.get(SESSION_COOKIE)
        if not token:
            return None

        now = int(time.time())
        with db.connect(self.server.db_path) as conn:
            row = db.get_session_with_user(conn, token)
            if not row:
                return None
            if int(row["expires_at"]) <= now:
                db.delete_session(conn, token)
                return None
            return AuthenticatedUser(id=int(row["user_id"]), username=str(row["username"]), role=str(row["role"]))

    def _require_user(self) -> AuthenticatedUser:
        user = self._get_current_user()
        if not user:
            raise PermissionError("not_authenticated")
        return user

    def _require_admin(self) -> AuthenticatedUser:
        user = self._require_user()
        if user.role != "admin":
            raise PermissionError("not_authorized")
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path)
            return
        self._handle_static_get(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return
        self._handle_api_post(parsed.path)

    def _handle_api_get(self, path: str) -> None:
        try:
            if path == "/api/me":
                user = self._require_user()
                self._send_json(HTTPStatus.OK, {"id": user.id, "username": user.username, "role": user.role})
                return

            if path == "/api/requests":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_requests(conn, user.id, user.role == "admin")
                self._send_json(HTTPStatus.OK, {"items": [_row_to_request(r) for r in rows]})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
        except PermissionError as e:
            code = str(e)
            if code == "not_authenticated":
                self._send_error(HTTPStatus.UNAUTHORIZED, "not_authenticated")
                return
            self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error")

    def _handle_api_post(self, path: str) -> None:
        try:
            if path == "/api/login":
                payload = _read_json(self) or {}
                username = str(payload.get("username", "")).strip()
                password = str(payload.get("password", ""))
                if not username or not password:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_credentials")
                    return

                with db.connect(self.server.db_path) as conn:
                    user = db.get_user_by_username(conn, username)
                    if not user or not verify_password(password, str(user["password_hash"])):
                        self._send_error(HTTPStatus.UNAUTHORIZED, "invalid_credentials")
                        return

                    token = new_session_token()
                    expires_at = int(time.time()) + SESSION_TTL_SECONDS
                    db.create_session(conn, token, int(user["id"]), expires_at)

                cookie = _build_session_cookie(token)
                self._send_json(
                    HTTPStatus.OK,
                    {"id": int(user["id"]), "username": str(user["username"]), "role": str(user["role"])},
                    headers={"Set-Cookie": cookie},
                )
                return

            if path == "/api/logout":
                cookies = parse_cookie_header(self.headers.get("Cookie"))
                token = cookies.get(SESSION_COOKIE)
                if token:
                    with db.connect(self.server.db_path) as conn:
                        db.delete_session(conn, token)
                self._send_empty(
                    HTTPStatus.NO_CONTENT,
                    headers={"Set-Cookie": _build_session_cookie("", expires_immediately=True)},
                )
                return

            if path == "/api/requests":
                user = self._require_user()
                payload = _read_json(self) or {}
                title = str(payload.get("title", "")).strip()
                body = str(payload.get("body", "")).strip()
                if not title or not body:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                with db.connect(self.server.db_path) as conn:
                    request_id = db.create_request(conn, user.id, title, body)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.CREATED, _row_to_request(row))
                return

            if path.startswith("/api/requests/") and path.endswith("/approve"):
                admin = self._require_admin()
                request_id = _parse_request_id(path, suffix="/approve")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    db.decide_request(conn, request_id, "approved", admin.id)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/requests/") and path.endswith("/reject"):
                admin = self._require_admin()
                request_id = _parse_request_id(path, suffix="/reject")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    db.decide_request(conn, request_id, "rejected", admin.id)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
        except json.JSONDecodeError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_json")
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_request_id")
        except PermissionError as e:
            code = str(e)
            if code == "not_authenticated":
                self._send_error(HTTPStatus.UNAUTHORIZED, "not_authenticated")
                return
            self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error")

    def _handle_static_get(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"

        rel = path.lstrip("/")
        candidate = (self.server.frontend_dir / rel).resolve()
        base = self.server.frontend_dir.resolve()
        if base not in candidate.parents and candidate != base:
            self._send_error(HTTPStatus.FORBIDDEN, "forbidden")
            return
        if not candidate.exists() or not candidate.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return

        ctype, _ = mimetypes.guess_type(str(candidate))
        if not ctype:
            ctype = "application/octet-stream"

        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text/") else ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _parse_request_id(path: str, suffix: str) -> int:
    core = path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def _row_to_request(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "status": str(row["status"]),
        "created_at": int(row["created_at"]),
        "owner": {"id": int(row["user_id"]), "username": str(row["owner_username"])},
        "decided_by": (
            None
            if row["decided_by"] is None
            else {"id": int(row["decided_by"]), "username": str(row["decided_by_username"])}
        ),
        "decided_at": None if row["decided_at"] is None else int(row["decided_at"]),
    }


def _build_session_cookie(token: str, expires_immediately: bool = False) -> str:
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax"]
    if os.environ.get("OA_COOKIE_SECURE") == "1":
        parts.append("Secure")
    if expires_immediately:
        parts.append("Max-Age=0")
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OA demo server (stdlib + sqlite)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(Path("data") / "oa.sqlite3"))
    parser.add_argument("--frontend", default=str(Path("frontend")))
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    frontend_dir = Path(args.frontend)
    db.init_db(db_path)

    httpd = OAHTTPServer((args.host, args.port), Handler, db_path=db_path, frontend_dir=frontend_dir)
    print(f"OA server running on http://{args.host}:{args.port}/")
    httpd.serve_forever()


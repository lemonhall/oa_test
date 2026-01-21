from __future__ import annotations

import json
import mimetypes
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .. import db
from ..auth import AuthenticatedUser, parse_cookie_header
from . import api_get, api_post
from .jsonutil import json_bytes
from .session import SESSION_COOKIE


class OAHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        db_path: Path,
        frontend_dir: Path,
        attachments_dir: Path | None = None,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.db_path = db_path
        self.frontend_dir = frontend_dir
        self.attachments_dir = attachments_dir or (db_path.parent / "attachments")
        self.attachments_dir.mkdir(parents=True, exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    server: OAHTTPServer  # type: ignore[assignment]

    def _send_json(self, status: int, payload, headers: dict[str, str] | None = None) -> None:
        body = json_bytes(payload)
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
            return AuthenticatedUser(
                id=int(row["user_id"]),
                username=str(row["username"]),
                role=str(row["role"]),
                dept=None if row["dept"] is None else str(row["dept"]),
                manager_id=None if row["manager_id"] is None else int(row["manager_id"]),
            )

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

    def _require_permission(self, permission_key: str) -> AuthenticatedUser:
        user = self._require_user()
        if user.role == "admin":
            return user
        with db.connect(self.server.db_path) as conn:
            if not db.role_has_permission(conn, user.role, permission_key):
                raise PermissionError("not_authorized")
        return user

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path, parsed.query)
            return
        self._handle_static_get(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return
        self._handle_api_post(parsed.path, parsed.query)

    def _handle_api_get(self, path: str, query: str) -> None:
        try:
            if api_get.handle(self, path, query):
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
        except PermissionError as e:
            code = str(e)
            if code == "not_authenticated":
                self._send_error(HTTPStatus.UNAUTHORIZED, "not_authenticated")
                return
            self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_id")
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error")

    def _handle_api_post(self, path: str, query: str) -> None:
        try:
            if api_post.handle(self, path, query):
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
        except json.JSONDecodeError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_json")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "not_found")
        except RuntimeError as e:
            if str(e) == "task_already_decided":
                self._send_error(HTTPStatus.CONFLICT, "task_already_decided")
                return
            if str(e) == "request_already_decided":
                self._send_error(HTTPStatus.CONFLICT, "request_already_decided")
                return
            self._send_error(HTTPStatus.CONFLICT, "conflict")
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_id")
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


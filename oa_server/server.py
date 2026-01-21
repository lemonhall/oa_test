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
from urllib.parse import parse_qs, urlparse

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
            if path == "/api/me":
                user = self._require_user()
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "id": user.id,
                        "username": user.username,
                        "role": user.role,
                        "dept": user.dept,
                        "manager_id": user.manager_id,
                    },
                )
                return

            if path == "/api/requests":
                user = self._require_user()
                params = parse_qs(query or "")
                scope = (params.get("scope", ["default"]) or ["default"])[0]
                if scope == "all":
                    if user.role != "admin":
                        raise PermissionError("not_authorized")
                    is_admin = True
                elif scope == "mine":
                    is_admin = False
                else:
                    is_admin = user.role == "admin"
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_requests(conn, user.id, is_admin)
                self._send_json(HTTPStatus.OK, {"items": [_row_to_request(r) for r in rows]})
                return

            if path.startswith("/api/requests/"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if user.role != "admin" and int(row["user_id"]) != user.id:
                        self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                        return
                    tasks = db.list_request_tasks(conn, request_id)
                    events = db.list_request_events(conn, request_id)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "request": _row_to_request(row),
                        "tasks": [_row_to_task(t) for t in tasks],
                        "events": [_row_to_event(e) for e in events],
                    },
                )
                return

            if path == "/api/inbox":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_inbox_tasks(conn, user_id=user.id, role=user.role)
                self._send_json(HTTPStatus.OK, {"items": [_row_to_inbox_task(r) for r in rows]})
                return

            if path == "/api/users":
                user = self._require_admin()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_users(conn)
                self._send_json(HTTPStatus.OK, {"items": [_row_to_user(r) for r in rows]})
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
                request_type = str(payload.get("type", "generic")).strip() or "generic"
                title = str(payload.get("title", "")).strip()
                body = str(payload.get("body", "")).strip()
                if not title or not body:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                with db.connect(self.server.db_path) as conn:
                    request_id = db.create_request(conn, user.id, request_type, title, body)
                    db.add_request_event(
                        conn,
                        request_id,
                        event_type="created",
                        actor_user_id=user.id,
                        message=f"type={request_type}",
                    )
                    _create_initial_task(conn, request_id, creator=user, request_type=request_type)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.CREATED, _row_to_request(row))
                return

            if path.startswith("/api/tasks/") and path.endswith("/approve"):
                user = self._require_user()
                task_id = _parse_task_id(path, suffix="/approve")
                payload = _read_json(self) or {}
                comment = None if payload is None else str(payload.get("comment", "")).strip() or None
                with db.connect(self.server.db_path) as conn:
                    row = _decide_task(conn, user, task_id, decision="approved", comment=comment)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/tasks/") and path.endswith("/reject"):
                user = self._require_user()
                task_id = _parse_task_id(path, suffix="/reject")
                payload = _read_json(self) or {}
                comment = None if payload is None else str(payload.get("comment", "")).strip() or None
                with db.connect(self.server.db_path) as conn:
                    row = _decide_task(conn, user, task_id, decision="rejected", comment=comment)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/requests/") and path.endswith("/approve"):
                # Backward compatible shortcut: approve the current pending task on the request.
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/approve")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row or row["pending_task_id"] is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    row = _decide_task(conn, user, int(row["pending_task_id"]), decision="approved", comment=None)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/requests/") and path.endswith("/reject"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/reject")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row or row["pending_task_id"] is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    row = _decide_task(conn, user, int(row["pending_task_id"]), decision="rejected", comment=None)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/users/"):
                self._require_admin()
                user_id = _parse_user_id(path, suffix="")
                payload = _read_json(self) or {}
                updates: dict[str, object] = {}
                if "dept" in payload:
                    dept = payload.get("dept")
                    updates["dept"] = None if dept is None else str(dept).strip()
                if "manager_id" in payload:
                    manager_id = payload.get("manager_id")
                    updates["manager_id"] = None if manager_id in (None, "") else int(manager_id)
                with db.connect(self.server.db_path) as conn:
                    if "manager_id" in updates and updates["manager_id"] is not None:
                        mgr = db.get_user_by_id(conn, int(updates["manager_id"]))
                        if not mgr:
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_manager_id")
                            return
                    db.update_user(conn, user_id, **updates)
                self._send_empty(HTTPStatus.NO_CONTENT)
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


def _parse_request_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])

def _parse_task_id(path: str, suffix: str) -> int:
    core = path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def _parse_user_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def _row_to_request(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "type": str(row["request_type"]) if "request_type" in row.keys() else "generic",
        "title": str(row["title"]),
        "body": str(row["body"]),
        "status": str(row["status"]),
        "created_at": int(row["created_at"]),
        "updated_at": None if row["updated_at"] is None else int(row["updated_at"]),
        "owner": {"id": int(row["user_id"]), "username": str(row["owner_username"])},
        "pending_task": (
            None
            if row["pending_task_id"] is None
            else {
                "id": int(row["pending_task_id"]),
                "step_key": str(row["pending_step_key"]),
                "assignee_user_id": None if row["pending_assignee_user_id"] is None else int(row["pending_assignee_user_id"]),
                "assignee_username": None
                if row["pending_assignee_username"] is None
                else str(row["pending_assignee_username"]),
                "assignee_role": None if row["pending_assignee_role"] is None else str(row["pending_assignee_role"]),
            }
        ),
        "decided_by": (
            None
            if row["decided_by"] is None
            else {"id": int(row["decided_by"]), "username": str(row["decided_by_username"])}
        ),
        "decided_at": None if row["decided_at"] is None else int(row["decided_at"]),
    }


def _row_to_task(row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "step_key": str(row["step_key"]),
        "assignee_user_id": None if row["assignee_user_id"] is None else int(row["assignee_user_id"]),
        "assignee_role": None if row["assignee_role"] is None else str(row["assignee_role"]),
        "assignee_username": None
        if "assignee_username" not in keys or row["assignee_username"] is None
        else str(row["assignee_username"]),
        "status": str(row["status"]),
        "decided_by": None if row["decided_by"] is None else int(row["decided_by"]),
        "decided_by_username": None
        if "decided_by_username" not in keys or row["decided_by_username"] is None
        else str(row["decided_by_username"]),
        "decided_at": None if row["decided_at"] is None else int(row["decided_at"]),
        "comment": None if row["comment"] is None else str(row["comment"]),
        "created_at": int(row["created_at"]),
    }


def _row_to_event(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "event_type": str(row["event_type"]),
        "actor_user_id": None if row["actor_user_id"] is None else int(row["actor_user_id"]),
        "actor_username": None if row["actor_username"] is None else str(row["actor_username"]),
        "message": None if row["message"] is None else str(row["message"]),
        "created_at": int(row["created_at"]),
    }


def _row_to_inbox_task(row) -> dict[str, Any]:
    return {
        "task": _row_to_task(row),
        "request": {
            "id": int(row["request_id"]),
            "type": str(row["request_type"]),
            "title": str(row["title"]),
            "body": str(row["body"]),
            "status": str(row["request_status"]),
            "created_at": int(row["request_created_at"]),
            "owner_username": str(row["owner_username"]),
        },
    }


def _row_to_user(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "role": str(row["role"]),
        "dept": None if row["dept"] is None else str(row["dept"]),
        "manager_id": None if row["manager_id"] is None else int(row["manager_id"]),
        "manager_username": None if row["manager_username"] is None else str(row["manager_username"]),
        "created_at": int(row["created_at"]),
    }


def _create_initial_task(conn, request_id: int, *, creator: AuthenticatedUser, request_type: str) -> None:
    step = "admin"
    assignee_user_id: int | None = None
    assignee_role: str | None = "admin"

    if request_type in {"leave", "expense"}:
        step = "manager"
        assignee_user_id = creator.manager_id
        assignee_role = None if assignee_user_id is not None else "admin"

    if request_type == "generic":
        step = "admin"
        assignee_user_id = None
        assignee_role = "admin"

    db.create_task(
        conn,
        request_id,
        step_key=step,
        assignee_user_id=assignee_user_id,
        assignee_role=assignee_role,
    )
    db.add_request_event(
        conn,
        request_id,
        event_type="task_created",
        actor_user_id=None,
        message=f"step={step}",
    )


def _next_step(request_type: str, current_step: str) -> str | None:
    if request_type == "expense" and current_step == "manager":
        return "finance"
    return None


def _step_assignee(step_key: str, *, creator: AuthenticatedUser) -> tuple[int | None, str | None]:
    if step_key == "manager":
        return (creator.manager_id, None if creator.manager_id is not None else "admin")
    if step_key == "finance":
        return (None, "admin")
    return (None, "admin")


def _can_act_on_task(user: AuthenticatedUser, task_row) -> bool:
    if task_row["assignee_user_id"] is not None and int(task_row["assignee_user_id"]) == user.id:
        return True
    if task_row["assignee_role"] is not None and str(task_row["assignee_role"]) == user.role:
        return True
    return False


def _decide_task(conn, user: AuthenticatedUser, task_id: int, *, decision: str, comment: str | None):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not _can_act_on_task(user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    db.decide_task(conn, task_id, status=decision, decided_by=user.id, comment=comment)
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_decided",
        actor_user_id=user.id,
        message=f"task={task_id} step={task['step_key']} decision={decision}",
    )

    if decision == "rejected":
        db.update_request_status(conn, int(task["request_id"]), status="rejected", decided_by=user.id)
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="request_rejected",
            actor_user_id=user.id,
            message=comment,
        )
        return db.get_request(conn, int(task["request_id"]))

    next_step = _next_step(str(req["request_type"]), str(task["step_key"]))
    if next_step:
        creator_row = db.get_user_by_id(conn, int(req["user_id"]))
        creator = AuthenticatedUser(
            id=int(creator_row["id"]),
            username=str(creator_row["username"]),
            role=str(creator_row["role"]),
            dept=None if creator_row["dept"] is None else str(creator_row["dept"]),
            manager_id=None if creator_row["manager_id"] is None else int(creator_row["manager_id"]),
        )
        assignee_user_id, assignee_role = _step_assignee(next_step, creator=creator)
        db.create_task(
            conn,
            int(task["request_id"]),
            step_key=next_step,
            assignee_user_id=assignee_user_id,
            assignee_role=assignee_role,
        )
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="task_created",
            actor_user_id=None,
            message=f"step={next_step}",
        )
        db.update_request_status(conn, int(task["request_id"]), status="pending", decided_by=None)
        return db.get_request(conn, int(task["request_id"]))

    db.update_request_status(conn, int(task["request_id"]), status="approved", decided_by=user.id)
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="request_approved",
        actor_user_id=user.id,
        message=comment,
    )
    return db.get_request(conn, int(task["request_id"]))


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

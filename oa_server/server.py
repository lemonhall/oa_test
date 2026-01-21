from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import time
import uuid
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


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _is_iso_date(value: str) -> bool:
    if len(value) != 10:
        return False
    # YYYY-MM-DD (lightweight check)
    return value[4] == "-" and value[7] == "-" and value[:4].isdigit() and value[5:7].isdigit() and value[8:10].isdigit()


def _build_request_from_payload(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any] | None,
) -> tuple[str, str, str | None]:
    if payload is None:
        return title, body, None

    if request_type == "leave":
        start_date = str(payload.get("start_date", "")).strip()
        end_date = str(payload.get("end_date", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        days_raw = payload.get("days", None)
        try:
            days = int(days_raw)
        except Exception:
            days = 0
        if not start_date or not end_date or not reason or days <= 0:
            raise ValueError("invalid_payload")
        if not _is_iso_date(start_date) or not _is_iso_date(end_date):
            raise ValueError("invalid_payload")

        if not title:
            title = f"请假：{start_date}~{end_date}（{days}天）"
        if not body:
            body = f"原因：{reason}"
        return title, body, _json_dumps(payload)

    if request_type == "expense":
        category = str(payload.get("category", "")).strip() or "报销"
        reason = str(payload.get("reason", "")).strip()
        amount_raw = payload.get("amount", None)
        try:
            amount = float(amount_raw)
        except Exception:
            amount = 0.0
        if amount <= 0:
            raise ValueError("invalid_payload")
        if not title:
            title = f"报销：{category} {amount:g}元"
        if not body:
            body = reason or f"类别：{category}"
        return title, body, _json_dumps(payload)

    if request_type == "purchase":
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("invalid_payload")
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise ValueError("invalid_payload")

        total = 0.0
        normalized_items: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                raise ValueError("invalid_payload")
            name = str(it.get("name", "")).strip()
            try:
                qty = int(it.get("qty", 0))
            except Exception:
                qty = 0
            try:
                unit_price = float(it.get("unit_price", 0))
            except Exception:
                unit_price = 0.0
            if not name or qty <= 0 or unit_price <= 0:
                raise ValueError("invalid_payload")
            line_total = qty * unit_price
            total += line_total
            normalized_items.append({"name": name, "qty": qty, "unit_price": unit_price, "line_total": line_total})

        if total <= 0:
            raise ValueError("invalid_payload")

        payload = dict(payload)
        payload["items"] = normalized_items
        payload["amount"] = float(payload.get("amount", total)) if payload.get("amount") is not None else total
        payload["amount"] = total  # canonical amount derived from items

        if not title:
            first = normalized_items[0]["name"]
            more = f"等{len(normalized_items)}项" if len(normalized_items) > 1 else ""
            title = f"采购：{first}{more} {total:g}元"
        if not body:
            body = f"原因：{reason}"
        return title, body, _json_dumps(payload)

    # generic/other: store as-is if provided
    return title, body, _json_dumps(payload)


def _parse_payload_json(req_row) -> dict[str, Any] | None:
    if "payload_json" not in req_row.keys() or req_row["payload_json"] is None:
        return None
    try:
        obj = json.loads(str(req_row["payload_json"]))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _step_condition_passes(step_row, request_payload: dict[str, Any] | None, *, creator_dept: str | None) -> bool:
    kind = None if step_row["condition_kind"] is None else str(step_row["condition_kind"]).strip()
    value = None if step_row["condition_value"] is None else str(step_row["condition_value"]).strip()
    if not kind:
        return True
    if kind == "min_amount":
        if not request_payload:
            return False
        try:
            amount = float(request_payload.get("amount"))
            threshold = float(value or "0")
        except Exception:
            return False
        return amount >= threshold
    if kind == "max_amount":
        if not request_payload:
            return False
        try:
            amount = float(request_payload.get("amount"))
            threshold = float(value or "0")
        except Exception:
            return False
        return amount <= threshold
    if kind == "min_days":
        if not request_payload:
            return False
        try:
            days = int(request_payload.get("days"))
            threshold = int(value or "0")
        except Exception:
            return False
        return days >= threshold
    if kind == "dept_in":
        if not creator_dept:
            return False
        allowed = []
        for part in (value or "").replace(";", ",").split(","):
            part = part.strip()
            if part:
                allowed.append(part.lower())
        if not allowed:
            return False
        return creator_dept.strip().lower() in allowed
    if kind == "category_in":
        if not request_payload:
            return False
        category = str(request_payload.get("category", "")).strip()
        allowed = []
        for part in (value or "").replace(";", ",").split(","):
            part = part.strip()
            if part:
                allowed.append(part.lower())
        if not allowed:
            return False
        return category.lower() in allowed
    # Unknown conditions default to True (safer than skipping required approvals)
    return True


def _find_next_step(steps, *, current_order: int | None, request_payload: dict[str, Any] | None, creator_dept: str | None):
    if not steps:
        return None
    for s in steps:
        if current_order is not None and int(s["step_order"]) <= int(current_order):
            continue
        if _step_condition_passes(s, request_payload, creator_dept=creator_dept):
            return s
    return None


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
            if path == "/api/me":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    permissions = ["*"] if user.role == "admin" else db.list_role_permissions(conn, user.role)
                self._send_json(
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
                return

            if path == "/api/workflows":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_available_workflow_variants(conn, dept=user.dept)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "items": [
                            {
                                "key": str(r["workflow_key"]),
                                "request_type": str(r["request_type"]),
                                "name": str(r["name"]),
                                "category": str(r["category"]),
                                "scope_kind": str(r["scope_kind"]),
                                "scope_value": None if r["scope_value"] is None else str(r["scope_value"]),
                                "is_default": bool(int(r["is_default"])),
                            }
                            for r in rows
                        ]
                    },
                )
                return

            if path == "/api/admin/workflows":
                self._require_permission("workflows:manage")
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_workflow_variants_admin(conn)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "items": [
                            {
                                "key": str(r["workflow_key"]),
                                "request_type": str(r["request_type"]),
                                "name": str(r["name"]),
                                "category": str(r["category"]),
                                "scope_kind": str(r["scope_kind"]),
                                "scope_value": None if r["scope_value"] is None else str(r["scope_value"]),
                                "enabled": bool(int(r["enabled"])),
                                "is_default": bool(int(r["is_default"])),
                            }
                            for r in rows
                        ]
                    },
                )
                return

            if path == "/api/admin/roles":
                self._require_permission("rbac:manage")
                with db.connect(self.server.db_path) as conn:
                    roles = db.list_roles(conn)
                    items = [{"role": str(r["name"]), "permissions": db.list_role_permissions(conn, str(r["name"]))} for r in roles]
                self._send_json(HTTPStatus.OK, {"items": items})
                return

            if path.startswith("/api/admin/workflows/"):
                self._require_permission("workflows:manage")
                workflow_key = path.split("/", 4)[-1]
                with db.connect(self.server.db_path) as conn:
                    wf = db.get_workflow_variant(conn, workflow_key)
                    if not wf:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    steps = db.list_workflow_variant_steps(conn, workflow_key)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "workflow": {
                            "key": str(wf["workflow_key"]),
                            "request_type": str(wf["request_type"]),
                            "name": str(wf["name"]),
                            "category": str(wf["category"]),
                            "scope_kind": str(wf["scope_kind"]),
                            "scope_value": None if wf["scope_value"] is None else str(wf["scope_value"]),
                            "enabled": bool(int(wf["enabled"])),
                            "is_default": bool(int(wf["is_default"])),
                        },
                        "steps": [
                            {
                                "step_order": int(s["step_order"]),
                                "step_key": str(s["step_key"]),
                                "assignee_kind": str(s["assignee_kind"]),
                                "assignee_value": None if s["assignee_value"] is None else str(s["assignee_value"]),
                                "condition_kind": None if s["condition_kind"] is None else str(s["condition_kind"]),
                                "condition_value": None if s["condition_value"] is None else str(s["condition_value"]),
                            }
                            for s in steps
                        ],
                    },
                )
                return

            if path == "/api/requests":
                user = self._require_user()
                params = parse_qs(query or "")
                scope = (params.get("scope", ["default"]) or ["default"])[0]
                with db.connect(self.server.db_path) as conn:
                    if scope == "all":
                        if user.role != "admin" and not db.role_has_permission(conn, user.role, "requests:read_all"):
                            raise PermissionError("not_authorized")
                        rows = db.list_requests(conn, user.id, True)
                    elif scope == "mine":
                        rows = db.list_requests(conn, user.id, False)
                    else:
                        rows = db.list_requests(conn, user.id, user.role == "admin")
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
                    attachments = db.list_request_attachments(conn, request_id)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "request": _row_to_request(row),
                        "tasks": [_row_to_task(t) for t in tasks],
                        "events": [_row_to_event(e) for e in events],
                        "attachments": [_row_to_attachment(a) for a in attachments],
                    },
                )
                return

            if path == "/api/inbox":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_inbox_tasks(conn, user_id=user.id, role=user.role)
                self._send_json(HTTPStatus.OK, {"items": [_row_to_inbox_task(r) for r in rows]})
                return

            if path == "/api/notifications":
                user = self._require_user()
                with db.connect(self.server.db_path) as conn:
                    rows = db.list_notifications(conn, user_id=user.id)
                self._send_json(HTTPStatus.OK, {"items": [_row_to_notification(r) for r in rows]})
                return

            if path.startswith("/api/attachments/") and path.endswith("/download"):
                user = self._require_user()
                attachment_id = _parse_attachment_id(path, suffix="/download")
                with db.connect(self.server.db_path) as conn:
                    att = db.get_attachment(conn, attachment_id)
                    if not att:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    req = db.get_request(conn, int(att["request_id"]))
                    if not req:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if user.role != "admin" and int(req["user_id"]) != user.id:
                        self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                        return

                rel = Path(str(att["storage_path"]))
                candidate = (self.server.attachments_dir / rel).resolve()
                base_dir = self.server.attachments_dir.resolve()
                if base_dir not in candidate.parents and candidate != base_dir:
                    self._send_error(HTTPStatus.FORBIDDEN, "forbidden")
                    return
                if not candidate.exists() or not candidate.is_file():
                    self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                    return

                data = candidate.read_bytes()
                ctype = "application/octet-stream"
                if att["content_type"] is not None and str(att["content_type"]).strip():
                    ctype = str(att["content_type"]).strip()
                safe = str(att["filename"]).replace('"', "").replace("\r", "").replace("\n", "")

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
                self.end_headers()
                self.wfile.write(data)
                return

            if path == "/api/users":
                user = self._require_permission("users:manage")
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
 
            if path == "/api/me/delegation":
                user = self._require_user()
                payload = _read_json(self) or {}
                delegate_user_id = payload.get("delegate_user_id", None)
                if delegate_user_id in (None, ""):
                    with db.connect(self.server.db_path) as conn:
                        db.set_delegation(conn, user.id, delegate_user_id=None, active=False)
                    self._send_json(HTTPStatus.CREATED, {"ok": True})
                    return
                try:
                    delegate_user_id_i = int(delegate_user_id)
                except Exception:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_id")
                    return
                if delegate_user_id_i == user.id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_delegate")
                    return
                with db.connect(self.server.db_path) as conn:
                    if not db.get_user_by_id(conn, delegate_user_id_i):
                        self._send_error(HTTPStatus.BAD_REQUEST, "invalid_delegate")
                        return
                    db.set_delegation(conn, user.id, delegate_user_id=delegate_user_id_i, active=True)
                self._send_json(HTTPStatus.CREATED, {"ok": True})
                return

            if path == "/api/requests":
                user = self._require_user()
                payload = _read_json(self) or {}
                requested_workflow = payload.get("workflow")
                request_type = str(payload.get("type", "generic")).strip() or "generic"
                title = str(payload.get("title", "")).strip()
                body = str(payload.get("body", "")).strip()
                req_payload = payload.get("payload", None)
                if req_payload is not None and not isinstance(req_payload, dict):
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                    return
                with db.connect(self.server.db_path) as conn:
                    workflow_key = None
                    if requested_workflow:
                        wf = db.get_workflow_variant(conn, str(requested_workflow))
                        if not wf or int(wf["enabled"]) != 1:
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_workflow")
                            return
                        request_type = str(wf["request_type"])
                        workflow_key = str(wf["workflow_key"])
                    else:
                        workflow_key = db.resolve_default_workflow_key(conn, request_type, dept=user.dept) or request_type

                    try:
                        title, body, payload_json = _build_request_from_payload(
                            request_type,
                            title=title,
                            body=body,
                            payload=req_payload,
                        )
                    except ValueError:
                        self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                        return
                    if not title or not body:
                        self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                        return

                    request_id = db.create_request(
                        conn,
                        user.id,
                        request_type,
                        title,
                        body,
                        payload_json=payload_json,
                        workflow_key=workflow_key,
                    )
                    db.add_request_event(
                        conn,
                        request_id,
                        event_type="created",
                        actor_user_id=user.id,
                        message=f"type={request_type} workflow={workflow_key}",
                    )
                    _create_initial_task(conn, request_id, creator=user, request_type=request_type, workflow_key=workflow_key)
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

            if path.startswith("/api/tasks/") and path.endswith("/addsign"):
                user = self._require_user()
                task_id = _parse_task_id(path, suffix="/addsign")
                payload = _read_json(self) or {}
                assignee_user_id = payload.get("assignee_user_id", None)
                if assignee_user_id in (None, ""):
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                with db.connect(self.server.db_path) as conn:
                    row = _add_sign(conn, user, task_id, assignee_user_id=int(assignee_user_id))
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/tasks/") and path.endswith("/transfer"):
                user = self._require_user()
                task_id = _parse_task_id(path, suffix="/transfer")
                payload = _read_json(self) or {}
                assignee_user_id = payload.get("assignee_user_id", None)
                if assignee_user_id in (None, ""):
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                with db.connect(self.server.db_path) as conn:
                    row = _transfer_task(conn, user, task_id, assignee_user_id=int(assignee_user_id))
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/tasks/") and path.endswith("/return"):
                user = self._require_user()
                task_id = _parse_task_id(path, suffix="/return")
                payload = _read_json(self) or {}
                comment = None if payload is None else str(payload.get("comment", "")).strip() or None
                with db.connect(self.server.db_path) as conn:
                    row = _return_for_changes(conn, user, task_id, comment=comment)
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

            if path.startswith("/api/requests/") and path.endswith("/resubmit"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/resubmit")
                payload = _read_json(self) or {}
                title = str(payload.get("title", "")).strip()
                body = str(payload.get("body", "")).strip()
                req_payload = payload.get("payload", None)
                if req_payload is not None and not isinstance(req_payload, dict):
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                    return
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if int(row["user_id"]) != user.id:
                        self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                        return
                    if str(row["status"]) != "changes_requested":
                        self._send_error(HTTPStatus.CONFLICT, "not_editable")
                        return
                    request_type = str(row["request_type"])
                    workflow_key = None if row["workflow_key"] is None else str(row["workflow_key"])
                    try:
                        title2, body2, payload_json = _build_request_from_payload(
                            request_type,
                            title=title,
                            body=body,
                            payload=req_payload,
                        )
                    except ValueError:
                        self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                        return
                    if not title2 or not body2:
                        self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                        return
                    db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
                    db.reset_request_for_resubmit(conn, request_id, title=title2, body=body2, payload_json=payload_json)
                    db.add_request_event(
                        conn,
                        request_id,
                        event_type="resubmitted",
                        actor_user_id=user.id,
                        message=None,
                    )
                    wk = workflow_key or db.resolve_default_workflow_key(conn, request_type, dept=user.dept) or request_type
                    _start_workflow(
                        conn,
                        request_id,
                        creator=user,
                        request_type=request_type,
                        workflow_key=wk,
                    )
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/requests/") and path.endswith("/watchers"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/watchers")
                payload = _read_json(self) or {}
                kind = str(payload.get("kind", "cc")).strip() or "cc"
                user_ids = payload.get("user_ids", None)
                if kind not in {"cc", "follow"}:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_kind")
                    return
                if not isinstance(user_ids, list) or not user_ids:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                try:
                    parsed_user_ids = [int(x) for x in user_ids]
                except Exception:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_user_ids")
                    return
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if user.role != "admin" and int(row["user_id"]) != user.id:
                        self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                        return
                    for uid in parsed_user_ids:
                        if not db.get_user_by_id(conn, int(uid)):
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_user_id")
                            return
                        db.add_request_watcher(conn, request_id, int(uid), kind=kind)
                self._send_json(HTTPStatus.CREATED, {"ok": True})
                return

            if path.startswith("/api/requests/") and path.endswith("/attachments"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/attachments")
                payload = _read_json(self) or {}
                filename = str(payload.get("filename", "")).strip()
                content_type = payload.get("content_type", None)
                content_type_s = None if content_type in (None, "") else str(content_type).strip()
                content_base64 = payload.get("content_base64", None)
                if not filename or not content_base64:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                if not isinstance(content_base64, str):
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                    return
                try:
                    row = _create_attachment(
                        self.server.attachments_dir,
                        user=user,
                        request_id=request_id,
                        filename=filename,
                        content_type=content_type_s,
                        content_base64=content_base64,
                        db_path=self.server.db_path,
                    )
                except ValueError:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                    return
                except FileNotFoundError:
                    self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                    return
                except PermissionError:
                    self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                    return
                self._send_json(HTTPStatus.CREATED, row)
                return

            if path.startswith("/api/requests/") and path.endswith("/withdraw"):
                user = self._require_user()
                request_id = _parse_request_id(path, suffix="/withdraw")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if int(row["user_id"]) != user.id:
                        self._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                        return
                    if str(row["status"]) not in {"pending", "changes_requested"}:
                        self._send_error(HTTPStatus.CONFLICT, "not_editable")
                        return
                    db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
                    db.update_request_status(conn, request_id, status="withdrawn", decided_by=None)
                    db.add_request_event(conn, request_id, event_type="withdrawn", actor_user_id=user.id, message=None)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/attachments/") and path.endswith("/download"):
                self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return

            if path.startswith("/api/requests/") and path.endswith("/void"):
                user = self._require_admin()
                request_id = _parse_request_id(path, suffix="/void")
                with db.connect(self.server.db_path) as conn:
                    row = db.get_request(conn, request_id)
                    if not row:
                        self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                        return
                    if str(row["status"]) not in {"pending", "changes_requested"}:
                        self._send_error(HTTPStatus.CONFLICT, "not_editable")
                        return
                    db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
                    db.update_request_status(conn, request_id, status="voided", decided_by=None)
                    db.add_request_event(conn, request_id, event_type="voided", actor_user_id=user.id, message=None)
                    row = db.get_request(conn, request_id)
                self._send_json(HTTPStatus.OK, _row_to_request(row))
                return

            if path.startswith("/api/notifications/") and path.endswith("/read"):
                user = self._require_user()
                notification_id = _parse_notification_id(path, suffix="/read")
                with db.connect(self.server.db_path) as conn:
                    ok = db.mark_notification_read(conn, notification_id, user_id=user.id)
                if not ok:
                    self._send_error(HTTPStatus.NOT_FOUND, "not_found")
                    return
                self._send_empty(HTTPStatus.NO_CONTENT)
                return

            if path.startswith("/api/users/"):
                self._require_permission("users:manage")
                user_id = _parse_user_id(path, suffix="")
                payload = _read_json(self) or {}
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
                with db.connect(self.server.db_path) as conn:
                    if "manager_id" in updates and updates["manager_id"] is not None:
                        mgr = db.get_user_by_id(conn, int(updates["manager_id"]))
                        if not mgr:
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_manager_id")
                            return
                    if "role" in updates:
                        role_v = updates["role"]
                        if role_v is None or not str(role_v).strip():
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_role")
                            return
                        if not db.role_exists(conn, str(role_v)):
                            self._send_error(HTTPStatus.BAD_REQUEST, "invalid_role")
                            return
                    db.update_user(conn, user_id, **updates)
                self._send_empty(HTTPStatus.NO_CONTENT)
                return

            if path == "/api/admin/workflows":
                self._require_permission("workflows:manage")
                payload = _read_json(self) or {}
                workflow_key = str(payload.get("workflow_key", "")).strip()
                request_type = str(payload.get("request_type", "")).strip()
                name = str(payload.get("name", "")).strip()
                category = str(payload.get("category", "")).strip() or "General"
                scope_kind = str(payload.get("scope_kind", "global")).strip() or "global"
                scope_value = payload.get("scope_value", None)
                scope_value_s = None if scope_value in (None, "") else str(scope_value).strip()
                enabled = bool(payload.get("enabled", True))
                is_default = bool(payload.get("is_default", False))
                steps = payload.get("steps", None)
                if not workflow_key or not request_type or not name:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                if scope_kind not in {"global", "dept"}:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_scope")
                    return
                if scope_kind == "dept" and not scope_value_s:
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_scope")
                    return
                if steps is not None and not isinstance(steps, list):
                    self._send_error(HTTPStatus.BAD_REQUEST, "invalid_steps")
                    return
                with db.connect(self.server.db_path) as conn:
                    db.upsert_workflow_variant(
                        conn,
                        workflow_key=workflow_key,
                        request_type=request_type,
                        name=name,
                        category=category,
                        scope_kind=scope_kind,
                        scope_value=scope_value_s,
                        enabled=enabled,
                        is_default=is_default,
                    )
                    if steps is not None:
                        db.replace_workflow_variant_steps(conn, workflow_key, steps)
                self._send_json(HTTPStatus.CREATED, {"ok": True})
                return

            if path == "/api/admin/roles":
                self._require_permission("rbac:manage")
                payload = _read_json(self) or {}
                role_name = str(payload.get("role", "")).strip()
                permissions = payload.get("permissions", None)
                if not role_name or not isinstance(permissions, list):
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                perms: list[str] = []
                for p in permissions:
                    if p in (None, ""):
                        continue
                    perms.append(str(p).strip())
                with db.connect(self.server.db_path) as conn:
                    db.upsert_role(conn, role_name)
                    db.replace_role_permissions(conn, role_name, perms)
                self._send_json(HTTPStatus.CREATED, {"ok": True})
                return

            if path == "/api/admin/workflows/delete":
                self._require_permission("workflows:manage")
                payload = _read_json(self) or {}
                workflow_key = str(payload.get("workflow_key", "")).strip()
                if not workflow_key:
                    self._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                    return
                with db.connect(self.server.db_path) as conn:
                    db.delete_workflow_variant(conn, workflow_key)
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

def _parse_notification_id(path: str, suffix: str) -> int:
    core = path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])

def _parse_attachment_id(path: str, suffix: str) -> int:
    core = path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def _parse_user_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def _row_to_request(row) -> dict[str, Any]:
    payload_obj = None
    if "payload_json" in row.keys() and row["payload_json"] is not None:
        try:
            payload_obj = json.loads(str(row["payload_json"]))
        except Exception:
            payload_obj = None
    keys = set(row.keys())
    return {
        "id": int(row["id"]),
        "type": str(row["request_type"]) if "request_type" in row.keys() else "generic",
        "workflow": (
            None
            if "workflow_key" not in keys or row["workflow_key"] is None
            else {
                "key": str(row["workflow_key"]),
                "name": None if "workflow_name" not in keys or row["workflow_name"] is None else str(row["workflow_name"]),
                "category": None
                if "workflow_category" not in keys or row["workflow_category"] is None
                else str(row["workflow_category"]),
                "scope_kind": None
                if "workflow_scope_kind" not in keys or row["workflow_scope_kind"] is None
                else str(row["workflow_scope_kind"]),
                "scope_value": None
                if "workflow_scope_value" not in keys or row["workflow_scope_value"] is None
                else str(row["workflow_scope_value"]),
            }
        ),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "payload": payload_obj,
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


def _row_to_notification(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": None if row["request_id"] is None else int(row["request_id"]),
        "event_type": str(row["event_type"]),
        "actor_user_id": None if row["actor_user_id"] is None else int(row["actor_user_id"]),
        "actor_username": None if row["actor_username"] is None else str(row["actor_username"]),
        "message": None if row["message"] is None else str(row["message"]),
        "created_at": int(row["created_at"]),
        "read_at": None if row["read_at"] is None else int(row["read_at"]),
    }

def _row_to_attachment(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "filename": str(row["filename"]),
        "content_type": None if row["content_type"] is None else str(row["content_type"]),
        "size": int(row["size"]),
        "uploader_user_id": int(row["uploader_user_id"]),
        "uploader_username": None
        if "uploader_username" not in row.keys() or row["uploader_username"] is None
        else str(row["uploader_username"]),
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


def _create_initial_task(
    conn,
    request_id: int,
    *,
    creator: AuthenticatedUser,
    request_type: str,
    workflow_key: str | None,
) -> None:
    wk = workflow_key
    if not wk:
        wk = db.resolve_default_workflow_key(conn, request_type, dept=creator.dept) or request_type
    _start_workflow(conn, request_id, creator=creator, request_type=request_type, workflow_key=wk)

def _resolve_assignee(creator: AuthenticatedUser, step_row) -> tuple[int | None, str | None]:
    kind = str(step_row["assignee_kind"])
    value = None if step_row["assignee_value"] is None else str(step_row["assignee_value"])
    if kind == "manager":
        if creator.manager_id is not None:
            return (creator.manager_id, None)
        return (None, "admin")
    if kind == "role":
        return (None, value or "admin")
    if kind == "user":
        return (int(value), None) if value else (None, "admin")
    return (None, "admin")


def _parse_int_list(value: str | None) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for part in str(value).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    seen = set()
    result: list[int] = []
    for i in out:
        if i in seen:
            continue
        seen.add(i)
        result.append(i)
    return result


def _create_tasks_for_step(conn, request_id: int, *, creator: AuthenticatedUser, step_row) -> str:
    step_order = int(step_row["step_order"])
    step_key = str(step_row["step_key"])
    kind = str(step_row["assignee_kind"])
    value = None if step_row["assignee_value"] is None else str(step_row["assignee_value"])

    if kind in {"users_all", "users_any"}:
        user_ids = _parse_int_list(value)
        if not user_ids:
            db.create_task(
                conn,
                request_id,
                step_order=step_order,
                step_key=step_key,
                assignee_user_id=None,
                assignee_role="admin",
            )
            return step_key
        for uid in user_ids:
            db.create_task(
                conn,
                request_id,
                step_order=step_order,
                step_key=step_key,
                assignee_user_id=uid,
                assignee_role=None,
            )
        return step_key

    assignee_user_id, assignee_role = _resolve_assignee(creator, step_row)
    db.create_task(
        conn,
        request_id,
        step_order=step_order,
        step_key=step_key,
        assignee_user_id=assignee_user_id,
        assignee_role=assignee_role,
    )
    return step_key


def _start_workflow(conn, request_id: int, *, creator: AuthenticatedUser, request_type: str, workflow_key: str) -> None:
    steps = db.list_workflow_variant_steps(conn, workflow_key)
    if not steps and workflow_key != request_type:
        steps = db.list_workflow_variant_steps(conn, request_type)
    if not steps:
        steps = db.list_workflow_variant_steps(conn, "generic")
    if not steps:
        step_order = 1
        step_key = "admin"
        assignee_user_id, assignee_role = (None, "admin")
    else:
        req = db.get_request(conn, request_id)
        request_payload = _parse_payload_json(req) if req else None
        step0 = _find_next_step(steps, current_order=None, request_payload=request_payload, creator_dept=creator.dept) or steps[0]
        step_order = int(step0["step_order"])
        step_key = str(step0["step_key"])
        assignee_user_id, assignee_role = _resolve_assignee(creator, step0)

    if steps:
        created_step_key = _create_tasks_for_step(conn, request_id, creator=creator, step_row=step0)
        db.add_request_event(
            conn,
            request_id,
            event_type="task_created",
            actor_user_id=None,
            message=f"step={created_step_key}",
        )
    else:
        db.create_task(
            conn,
            request_id,
            step_order=step_order,
            step_key=step_key,
            assignee_user_id=assignee_user_id,
            assignee_role=assignee_role,
        )
        db.add_request_event(conn, request_id, event_type="task_created", actor_user_id=None, message=f"step={step_key}")


def _can_act_on_task(user: AuthenticatedUser, task_row) -> bool:
    if task_row["assignee_user_id"] is not None and int(task_row["assignee_user_id"]) == user.id:
        return True
    if task_row["assignee_role"] is not None and str(task_row["assignee_role"]) == user.role:
        return True
    return False


def _can_act_on_task_with_delegation(conn, user: AuthenticatedUser, task_row) -> bool:
    if _can_act_on_task(user, task_row):
        return True
    if task_row["assignee_user_id"] is None:
        return False
    return db.is_active_delegate(conn, int(task_row["assignee_user_id"]), int(user.id))


def _sanitize_filename(filename: str) -> str:
    name = str(filename).replace("\\", "/").split("/")[-1].strip()
    if not name:
        return "file"
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {" ", ".", "_", "-"}:
            safe.append(ch)
        else:
            safe.append("_")
    out = "".join(safe).strip(" .")
    return (out or "file")[:200]


def _create_attachment(
    attachments_dir: Path,
    *,
    user: AuthenticatedUser,
    request_id: int,
    filename: str,
    content_type: str | None,
    content_base64: str,
    db_path: Path,
) -> dict[str, Any]:
    with db.connect(db_path) as conn:
        req = db.get_request(conn, request_id)
        if not req:
            raise FileNotFoundError("not_found")
        if user.role != "admin" and int(req["user_id"]) != user.id:
            raise PermissionError("not_authorized")

        try:
            data = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except Exception:
            raise ValueError("invalid_payload")
        if len(data) > 5 * 1024 * 1024:
            raise ValueError("too_large")

        safe_name = _sanitize_filename(filename)
        req_dir = attachments_dir / str(request_id)
        req_dir.mkdir(parents=True, exist_ok=True)
        key = None
        final = None
        for _ in range(5):
            candidate_key = uuid.uuid4().hex
            candidate_path = req_dir / candidate_key
            if candidate_path.exists():
                continue
            candidate_path.write_bytes(data)
            key = candidate_key
            final = candidate_path
            break
        if not key or final is None:
            raise RuntimeError("storage_error")

        storage_path = f"{request_id}/{key}"
        att_id = db.create_attachment(
            conn,
            request_id,
            uploader_user_id=user.id,
            filename=safe_name,
            content_type=content_type,
            size=len(data),
            storage_path=storage_path,
        )
        row = db.get_attachment(conn, att_id)
        return {
            "id": int(row["id"]),
            "request_id": int(row["request_id"]),
            "filename": str(row["filename"]),
            "content_type": None if row["content_type"] is None else str(row["content_type"]),
            "size": int(row["size"]),
            "created_at": int(row["created_at"]),
        }


def _transfer_task(conn, user: AuthenticatedUser, task_id: int, *, assignee_user_id: int):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if user.role != "admin" and not _can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    if not db.get_user_by_id(conn, int(assignee_user_id)):
        raise FileNotFoundError("user_not_found")

    db.transfer_task(conn, int(task_id), assignee_user_id=int(assignee_user_id))
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_transferred",
        actor_user_id=user.id,
        message=f"task={task_id} to_user_id={assignee_user_id}",
    )
    return db.get_request(conn, int(task["request_id"]))


def _add_sign(conn, user: AuthenticatedUser, task_id: int, *, assignee_user_id: int):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not _can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    if not db.get_user_by_id(conn, int(assignee_user_id)):
        raise FileNotFoundError("user_not_found")

    db.create_task(
        conn,
        int(task["request_id"]),
        step_order=None if task["step_order"] is None else int(task["step_order"]),
        step_key=str(task["step_key"]),
        assignee_user_id=int(assignee_user_id),
        assignee_role=None,
    )
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_addsigned",
        actor_user_id=user.id,
        message=f"task={task_id} to_user_id={assignee_user_id}",
    )
    return db.get_request(conn, int(task["request_id"]))


def _return_for_changes(conn, user: AuthenticatedUser, task_id: int, *, comment: str | None):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not _can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    request_id = int(task["request_id"])
    req = db.get_request(conn, request_id)
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    db.decide_task(conn, task_id, status="returned", decided_by=user.id, comment=comment)
    db.add_request_event(
        conn,
        request_id,
        event_type="task_returned",
        actor_user_id=user.id,
        message=f"task={task_id} step={task['step_key']}",
    )

    db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
    db.mark_request_changes_requested(conn, request_id)
    db.add_request_event(
        conn,
        request_id,
        event_type="changes_requested",
        actor_user_id=user.id,
        message=comment,
    )
    db.create_resubmit_task(conn, request_id, int(req["user_id"]))
    db.add_request_event(conn, request_id, event_type="task_created", actor_user_id=None, message="step=resubmit")
    return db.get_request(conn, request_id)


def _decide_task(conn, user: AuthenticatedUser, task_id: int, *, decision: str, comment: str | None):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not _can_act_on_task_with_delegation(conn, user, task):
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

    request_type = str(req["request_type"])
    workflow_key = str(req["workflow_key"]) if "workflow_key" in req.keys() and req["workflow_key"] else None
    if not workflow_key:
        workflow_key = db.resolve_default_workflow_key(conn, request_type, dept=user.dept) or request_type
    steps = db.list_workflow_variant_steps(conn, workflow_key)
    if not steps and workflow_key != request_type:
        steps = db.list_workflow_variant_steps(conn, request_type)
    if not steps:
        steps = db.list_workflow_variant_steps(conn, "generic")

    current_order = task["step_order"]
    if current_order is None:
        current_order = None
        for s in steps:
            if str(s["step_key"]) == str(task["step_key"]):
                current_order = int(s["step_order"])
                break

    request_payload = _parse_payload_json(req)
    creator_row = db.get_user_by_id(conn, int(req["user_id"]))
    creator_dept = None if creator_row["dept"] is None else str(creator_row["dept"])

    current_step_row = None
    if current_order is not None:
        for s in steps:
            if int(s["step_order"]) == int(current_order):
                current_step_row = s
                break
    current_assignee_kind = None if not current_step_row else str(current_step_row["assignee_kind"])
    is_users_any = current_assignee_kind == "users_any"
    is_users_all = current_assignee_kind == "users_all"

    if decision == "rejected":
        if is_users_any and current_order is not None:
            group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
            pending_left = any(str(t["status"]) == "pending" for t in group)
            approved_any = any(str(t["status"]) == "approved" for t in group)
            if pending_left or approved_any:
                return db.get_request(conn, int(task["request_id"]))

        db.update_request_status(conn, int(task["request_id"]), status="rejected", decided_by=user.id)
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="request_rejected",
            actor_user_id=user.id,
            message=comment,
        )
        return db.get_request(conn, int(task["request_id"]))

    if is_users_all and current_order is not None:
        group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
        if group and not all(str(t["status"]) == "approved" for t in group):
            return db.get_request(conn, int(task["request_id"]))

    if is_users_any and current_order is not None:
        db.cancel_pending_tasks_for_step(
            conn,
            int(task["request_id"]),
            int(current_order),
            except_task_id=int(task_id),
            decided_by=user.id,
        )

    if current_order is not None:
        group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
        if any(str(t["status"]) == "pending" for t in group):
            return db.get_request(conn, int(task["request_id"]))

    next_step_row = _find_next_step(steps, current_order=current_order, request_payload=request_payload, creator_dept=creator_dept)

    if next_step_row is not None:
        creator = AuthenticatedUser(
            id=int(creator_row["id"]),
            username=str(creator_row["username"]),
            role=str(creator_row["role"]),
            dept=None if creator_row["dept"] is None else str(creator_row["dept"]),
            manager_id=None if creator_row["manager_id"] is None else int(creator_row["manager_id"]),
        )
        _create_tasks_for_step(conn, int(task["request_id"]), creator=creator, step_row=next_step_row)
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="task_created",
            actor_user_id=None,
            message=f"step={next_step_row['step_key']}",
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

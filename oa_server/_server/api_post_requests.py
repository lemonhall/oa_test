from __future__ import annotations

from http import HTTPStatus

from .. import db
from .attachments import create_attachment
from .ids import parse_request_id
from .jsonutil import read_json
from .payloads import build_request_from_payload
from .serializers import row_to_request
from .task_actions import decide_task
from .workflow_engine import create_initial_task, start_workflow


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/requests":
        user = handler._require_user()
        payload = read_json(handler) or {}
        requested_workflow = payload.get("workflow")
        request_type = str(payload.get("type", "generic")).strip() or "generic"
        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()
        req_payload = payload.get("payload", None)
        if req_payload is not None and not isinstance(req_payload, dict):
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
            return True

        with db.connect(handler.server.db_path) as conn:
            workflow_key = None
            if requested_workflow:
                wf = db.get_workflow_variant(conn, str(requested_workflow))
                if not wf or int(wf["enabled"]) != 1:
                    handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_workflow")
                    return True
                request_type = str(wf["request_type"])
                workflow_key = str(wf["workflow_key"])
            else:
                workflow_key = db.resolve_default_workflow_key(conn, request_type, dept=user.dept) or request_type

            try:
                title, body, payload_json = build_request_from_payload(
                    request_type,
                    title=title,
                    body=body,
                    payload=req_payload,
                )
            except ValueError:
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                return True
            if not title or not body:
                handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                return True

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
            create_initial_task(conn, request_id, creator=user, request_type=request_type, workflow_key=workflow_key)
            row = db.get_request(conn, request_id)
        handler._send_json(HTTPStatus.CREATED, row_to_request(row))
        return True

    if path.startswith("/api/requests/") and path.endswith("/approve"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/approve")
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row or row["pending_task_id"] is None:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            row = decide_task(conn, user, int(row["pending_task_id"]), decision="approved", comment=None)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/requests/") and path.endswith("/reject"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/reject")
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row or row["pending_task_id"] is None:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            row = decide_task(conn, user, int(row["pending_task_id"]), decision="rejected", comment=None)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/requests/") and path.endswith("/resubmit"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/resubmit")
        payload = read_json(handler) or {}
        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()
        req_payload = payload.get("payload", None)
        if req_payload is not None and not isinstance(req_payload, dict):
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
            return True
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            if int(row["user_id"]) != user.id:
                handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                return True
            if str(row["status"]) != "changes_requested":
                handler._send_error(HTTPStatus.CONFLICT, "not_editable")
                return True
            request_type = str(row["request_type"])
            workflow_key = None if row["workflow_key"] is None else str(row["workflow_key"])
            try:
                title2, body2, payload_json = build_request_from_payload(
                    request_type,
                    title=title,
                    body=body,
                    payload=req_payload,
                )
            except ValueError:
                handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
                return True
            if not title2 or not body2:
                handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
                return True
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
            start_workflow(conn, request_id, creator=user, request_type=request_type, workflow_key=wk)
            row = db.get_request(conn, request_id)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/requests/") and path.endswith("/watchers"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/watchers")
        payload = read_json(handler) or {}
        kind = str(payload.get("kind", "cc")).strip() or "cc"
        user_ids = payload.get("user_ids", None)
        if kind not in {"cc", "follow"}:
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_kind")
            return True
        if not isinstance(user_ids, list) or not user_ids:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        try:
            parsed_user_ids = [int(x) for x in user_ids]
        except Exception:
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_user_ids")
            return True
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            if user.role != "admin" and int(row["user_id"]) != user.id:
                handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                return True
            for uid in parsed_user_ids:
                if not db.get_user_by_id(conn, int(uid)):
                    handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_user_id")
                    return True
                db.add_request_watcher(conn, request_id, int(uid), kind=kind)
        handler._send_json(HTTPStatus.CREATED, {"ok": True})
        return True

    if path.startswith("/api/requests/") and path.endswith("/attachments"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/attachments")
        payload = read_json(handler) or {}
        filename = str(payload.get("filename", "")).strip()
        content_type = payload.get("content_type", None)
        content_type_s = None if content_type in (None, "") else str(content_type).strip()
        content_base64 = payload.get("content_base64", None)
        if not filename or not content_base64:
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        if not isinstance(content_base64, str):
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
            return True
        try:
            row = create_attachment(
                handler.server.attachments_dir,
                user=user,
                request_id=request_id,
                filename=filename,
                content_type=content_type_s,
                content_base64=content_base64,
                db_path=handler.server.db_path,
            )
        except ValueError:
            handler._send_error(HTTPStatus.BAD_REQUEST, "invalid_payload")
            return True
        except FileNotFoundError:
            handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return True
        except PermissionError:
            handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
            return True
        handler._send_json(HTTPStatus.CREATED, row)
        return True

    if path.startswith("/api/requests/") and path.endswith("/withdraw"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="/withdraw")
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            if int(row["user_id"]) != user.id:
                handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                return True
            if str(row["status"]) not in {"pending", "changes_requested"}:
                handler._send_error(HTTPStatus.CONFLICT, "not_editable")
                return True
            db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
            db.update_request_status(conn, request_id, status="withdrawn", decided_by=None)
            db.add_request_event(conn, request_id, event_type="withdrawn", actor_user_id=user.id, message=None)
            row = db.get_request(conn, request_id)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/requests/") and path.endswith("/void"):
        user = handler._require_admin()
        request_id = parse_request_id(path, suffix="/void")
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            if str(row["status"]) not in {"pending", "changes_requested"}:
                handler._send_error(HTTPStatus.CONFLICT, "not_editable")
                return True
            db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
            db.update_request_status(conn, request_id, status="voided", decided_by=None)
            db.add_request_event(conn, request_id, event_type="voided", actor_user_id=user.id, message=None)
            row = db.get_request(conn, request_id)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    return False


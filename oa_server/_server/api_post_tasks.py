from __future__ import annotations

from http import HTTPStatus

from .. import db
from .ids import parse_task_id
from .jsonutil import read_json
from .serializers import row_to_request
from .task_actions import add_sign, decide_task, return_for_changes, transfer_task


def try_handle(handler, path: str, query: str) -> bool:
    if path.startswith("/api/tasks/") and path.endswith("/approve"):
        user = handler._require_user()
        task_id = parse_task_id(path, suffix="/approve")
        payload = read_json(handler) or {}
        comment = None if payload is None else str(payload.get("comment", "")).strip() or None
        with db.connect(handler.server.db_path) as conn:
            row = decide_task(conn, user, task_id, decision="approved", comment=comment)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/tasks/") and path.endswith("/reject"):
        user = handler._require_user()
        task_id = parse_task_id(path, suffix="/reject")
        payload = read_json(handler) or {}
        comment = None if payload is None else str(payload.get("comment", "")).strip() or None
        with db.connect(handler.server.db_path) as conn:
            row = decide_task(conn, user, task_id, decision="rejected", comment=comment)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/tasks/") and path.endswith("/return"):
        user = handler._require_user()
        task_id = parse_task_id(path, suffix="/return")
        payload = read_json(handler) or {}
        comment = None if payload is None else str(payload.get("comment", "")).strip() or None
        with db.connect(handler.server.db_path) as conn:
            row = return_for_changes(conn, user, task_id, comment=comment)
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/tasks/") and path.endswith("/addsign"):
        user = handler._require_user()
        task_id = parse_task_id(path, suffix="/addsign")
        payload = read_json(handler) or {}
        assignee_user_id = payload.get("assignee_user_id", None)
        if assignee_user_id in (None, ""):
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        with db.connect(handler.server.db_path) as conn:
            row = add_sign(conn, user, task_id, assignee_user_id=int(assignee_user_id))
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    if path.startswith("/api/tasks/") and path.endswith("/transfer"):
        user = handler._require_user()
        task_id = parse_task_id(path, suffix="/transfer")
        payload = read_json(handler) or {}
        assignee_user_id = payload.get("assignee_user_id", None)
        if assignee_user_id in (None, ""):
            handler._send_error(HTTPStatus.BAD_REQUEST, "missing_fields")
            return True
        with db.connect(handler.server.db_path) as conn:
            row = transfer_task(conn, user, task_id, assignee_user_id=int(assignee_user_id))
        handler._send_json(HTTPStatus.OK, row_to_request(row))
        return True

    return False


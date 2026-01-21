from __future__ import annotations

import csv
import io
from http import HTTPStatus
from urllib.parse import parse_qs

from .. import db
from .ids import parse_request_id
from .serializers import row_to_attachment, row_to_event, row_to_request, row_to_task


def try_handle(handler, path: str, query: str) -> bool:
    if path == "/api/requests":
        user = handler._require_user()
        params = parse_qs(query or "")
        scope = (params.get("scope", ["default"]) or ["default"])[0]
        q = (params.get("q", [""]) or [""])[0].strip()
        out_format = (params.get("format", ["json"]) or ["json"])[0].strip().lower()
        with db.connect(handler.server.db_path) as conn:
            if scope == "all":
                if user.role != "admin" and not db.role_has_permission(conn, user.role, "requests:read_all"):
                    raise PermissionError("not_authorized")
                rows = db.list_requests(conn, user.id, True)
            elif scope == "mine":
                rows = db.list_requests(conn, user.id, False)
            else:
                rows = db.list_requests(conn, user.id, user.role == "admin")
        if q:
            ql = q.lower()
            rows = [r for r in rows if ql in str(r["title"]).lower() or ql in str(r["body"]).lower()]

        if out_format == "csv":
            items = [row_to_request(r) for r in rows]
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(["id", "type", "title", "body", "status", "owner_username", "created_at"])
            for it in items:
                w.writerow([it["id"], it["type"], it["title"], it["body"], it["status"], it["owner"]["username"], it["created_at"]])
            data = buf.getvalue().encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/csv; charset=utf-8")
            handler.send_header("Content-Length", str(len(data)))
            handler.send_header("Content-Disposition", 'attachment; filename="requests.csv"')
            handler.end_headers()
            handler.wfile.write(data)
            return True

        handler._send_json(HTTPStatus.OK, {"items": [row_to_request(r) for r in rows]})
        return True

    if path.startswith("/api/requests/"):
        user = handler._require_user()
        request_id = parse_request_id(path, suffix="")
        with db.connect(handler.server.db_path) as conn:
            row = db.get_request(conn, request_id)
            if not row:
                handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
                return True
            if user.role != "admin" and int(row["user_id"]) != user.id:
                handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
                return True
            tasks = db.list_request_tasks(conn, request_id)
            events = db.list_request_events(conn, request_id)
            attachments = db.list_request_attachments(conn, request_id)
        handler._send_json(
            HTTPStatus.OK,
            {
                "request": row_to_request(row),
                "tasks": [row_to_task(t) for t in tasks],
                "events": [row_to_event(e) for e in events],
                "attachments": [row_to_attachment(a) for a in attachments],
            },
        )
        return True

    return False


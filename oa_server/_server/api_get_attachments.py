from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from .. import db
from .ids import parse_attachment_id


def try_handle(handler, path: str, query: str) -> bool:
    if not (path.startswith("/api/attachments/") and path.endswith("/download")):
        return False

    user = handler._require_user()
    attachment_id = parse_attachment_id(path, suffix="/download")
    with db.connect(handler.server.db_path) as conn:
        att = db.get_attachment(conn, attachment_id)
        if not att:
            handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return True
        req = db.get_request(conn, int(att["request_id"]))
        if not req:
            handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
            return True
        if user.role != "admin" and int(req["user_id"]) != user.id:
            handler._send_error(HTTPStatus.FORBIDDEN, "not_authorized")
            return True

    rel = Path(str(att["storage_path"]))
    candidate = (handler.server.attachments_dir / rel).resolve()
    base_dir = handler.server.attachments_dir.resolve()
    if base_dir not in candidate.parents and candidate != base_dir:
        handler._send_error(HTTPStatus.FORBIDDEN, "forbidden")
        return True
    if not candidate.exists() or not candidate.is_file():
        handler._send_error(HTTPStatus.NOT_FOUND, "not_found")
        return True

    data = candidate.read_bytes()
    ctype = "application/octet-stream"
    if att["content_type"] is not None and str(att["content_type"]).strip():
        ctype = str(att["content_type"]).strip()
    safe = str(att["filename"]).replace('"', "").replace("\r", "").replace("\n", "")

    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Content-Disposition", f'attachment; filename="{safe}"')
    handler.end_headers()
    handler.wfile.write(data)
    return True


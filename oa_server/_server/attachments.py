from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any

from .. import db
from ..auth import AuthenticatedUser


def sanitize_filename(filename: str) -> str:
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


def create_attachment(
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

        safe_name = sanitize_filename(filename)
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


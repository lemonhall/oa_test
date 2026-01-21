from __future__ import annotations

import sqlite3
import time


def create_attachment(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    uploader_user_id: int,
    filename: str,
    content_type: str | None,
    size: int,
    storage_path: str,
) -> int:
    now = int(time.time())
    cur = conn.execute(
        """
        INSERT INTO attachments(request_id,uploader_user_id,filename,content_type,size,storage_path,created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (request_id, uploader_user_id, filename, content_type, size, storage_path, now),
    )
    return int(cur.lastrowid)


def get_attachment(conn: sqlite3.Connection, attachment_id: int):
    return conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()


def list_request_attachments(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT a.*, u.username AS uploader_username
        FROM attachments a
        JOIN users u ON u.id = a.uploader_user_id
        WHERE a.request_id = ?
        ORDER BY a.id ASC
        """,
        (request_id,),
    ).fetchall()


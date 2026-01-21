from __future__ import annotations

import sqlite3
import time


def add_request_event(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    event_type: str,
    actor_user_id: int | None,
    message: str | None,
) -> None:
    now = int(time.time())
    conn.execute(
        "INSERT INTO request_events(request_id,event_type,actor_user_id,message,created_at) VALUES(?,?,?,?,?)",
        (request_id, event_type, actor_user_id, message, now),
    )
    _notify_for_request_event(
        conn,
        request_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        message=message,
        created_at=now,
    )


def add_request_watcher(conn: sqlite3.Connection, request_id: int, user_id: int, *, kind: str) -> None:
    now = int(time.time())
    conn.execute(
        "INSERT OR IGNORE INTO request_watchers(request_id,user_id,kind,created_at) VALUES(?,?,?,?)",
        (request_id, user_id, kind, now),
    )


def list_request_watchers(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT w.*, u.username
        FROM request_watchers w
        JOIN users u ON u.id = w.user_id
        WHERE w.request_id = ?
        ORDER BY w.created_at ASC
        """,
        (request_id,),
    ).fetchall()


def _notify_for_request_event(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    event_type: str,
    actor_user_id: int | None,
    message: str | None,
    created_at: int,
) -> None:
    notify_types = {
        "changes_requested",
        "resubmitted",
        "withdrawn",
        "voided",
        "request_approved",
        "request_rejected",
        "task_transferred",
    }
    if event_type not in notify_types:
        return

    owner_row = conn.execute("SELECT user_id FROM requests WHERE id=?", (request_id,)).fetchone()
    owner_user_id = None if not owner_row else int(owner_row["user_id"])

    watcher_rows = conn.execute("SELECT user_id FROM request_watchers WHERE request_id=?", (request_id,)).fetchall()
    recipients = {int(r["user_id"]) for r in watcher_rows}
    if owner_user_id is not None:
        recipients.add(owner_user_id)
    if actor_user_id is not None:
        recipients.discard(int(actor_user_id))
    if not recipients:
        return

    conn.executemany(
        """
        INSERT INTO notifications(user_id,request_id,event_type,actor_user_id,message,created_at,read_at)
        VALUES(?,?,?,?,?,?,NULL)
        """,
        [(uid, request_id, event_type, actor_user_id, message, created_at) for uid in sorted(recipients)],
    )


def list_request_events(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT e.*, u.username AS actor_username
        FROM request_events e
        LEFT JOIN users u ON u.id = e.actor_user_id
        WHERE e.request_id = ?
        ORDER BY e.id ASC
        """,
        (request_id,),
    ).fetchall()


from __future__ import annotations

import sqlite3
import time


def list_notifications(conn: sqlite3.Connection, *, user_id: int, limit: int = 200):
    return conn.execute(
        """
        SELECT
          n.*,
          au.username AS actor_username
        FROM notifications n
        LEFT JOIN users au ON au.id = n.actor_user_id
        WHERE n.user_id = ?
        ORDER BY n.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()


def mark_notification_read(conn: sqlite3.Connection, notification_id: int, *, user_id: int) -> bool:
    now = int(time.time())
    cur = conn.execute(
        "UPDATE notifications SET read_at=? WHERE id=? AND user_id=? AND read_at IS NULL",
        (now, notification_id, user_id),
    )
    if cur.rowcount and int(cur.rowcount) > 0:
        return True
    row = conn.execute("SELECT 1 FROM notifications WHERE id=? AND user_id=?", (notification_id, user_id)).fetchone()
    return row is not None


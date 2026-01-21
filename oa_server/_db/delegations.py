from __future__ import annotations

import sqlite3
import time


def set_delegation(conn: sqlite3.Connection, delegator_user_id: int, *, delegate_user_id: int | None, active: bool) -> None:
    now = int(time.time())
    if active and delegate_user_id is None:
        raise ValueError("missing_delegate")
    existing = conn.execute(
        "SELECT 1 FROM delegations WHERE delegator_user_id=? LIMIT 1",
        (delegator_user_id,),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE delegations SET delegate_user_id=?, active=?, revoked_at=? WHERE delegator_user_id=?",
            (delegate_user_id, 1 if active else 0, None if active else now, delegator_user_id),
        )
        return
    conn.execute(
        "INSERT INTO delegations(delegator_user_id,delegate_user_id,active,created_at,revoked_at) VALUES(?,?,?,?,?)",
        (delegator_user_id, delegate_user_id, 1 if active else 0, now, None if active else now),
    )


def get_delegation(conn: sqlite3.Connection, delegator_user_id: int):
    return conn.execute("SELECT * FROM delegations WHERE delegator_user_id=?", (delegator_user_id,)).fetchone()


def is_active_delegate(conn: sqlite3.Connection, delegator_user_id: int, delegate_user_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM delegations
        WHERE delegator_user_id=? AND delegate_user_id=? AND active=1
        LIMIT 1
        """,
        (delegator_user_id, delegate_user_id),
    ).fetchone()
    return row is not None


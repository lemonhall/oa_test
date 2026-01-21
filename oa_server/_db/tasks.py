from __future__ import annotations

import sqlite3
import time


def create_task(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    step_order: int | None,
    step_key: str,
    assignee_user_id: int | None,
    assignee_role: str | None,
) -> int:
    now = int(time.time())
    cur = conn.execute(
        """
        INSERT INTO tasks(request_id,step_order,step_key,assignee_user_id,assignee_role,status,created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (request_id, step_order, step_key, assignee_user_id, assignee_role, "pending", now),
    )
    return int(cur.lastrowid)


def list_inbox_tasks(conn: sqlite3.Connection, *, user_id: int, role: str):
    return conn.execute(
        """
        SELECT
          t.*,
          r.request_type, r.title, r.body, r.status AS request_status, r.created_at AS request_created_at,
          u.username AS owner_username,
          au.username AS assignee_username
        FROM tasks t
        JOIN requests r ON r.id = t.request_id
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users au ON au.id = t.assignee_user_id
        WHERE t.status='pending'
          AND (
            r.status='pending'
            OR (r.status='changes_requested' AND t.step_key='resubmit')
          )
          AND (
            t.assignee_user_id = ?
            OR (t.assignee_role IS NOT NULL AND t.assignee_role = ?)
            OR (
              t.assignee_user_id IS NOT NULL
              AND t.assignee_user_id IN (
                SELECT delegator_user_id FROM delegations WHERE delegate_user_id=? AND active=1
              )
            )
          )
        ORDER BY t.id DESC
        """,
        (user_id, role, user_id),
    ).fetchall()


def get_task(conn: sqlite3.Connection, task_id: int):
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def decide_task(conn: sqlite3.Connection, task_id: int, *, status: str, decided_by: int, comment: str | None) -> None:
    now = int(time.time())
    conn.execute(
        """
        UPDATE tasks
        SET status=?, decided_by=?, decided_at=?, comment=?
        WHERE id=? AND status='pending'
        """,
        (status, decided_by, now, comment, task_id),
    )


def transfer_task(conn: sqlite3.Connection, task_id: int, *, assignee_user_id: int) -> None:
    conn.execute(
        """
        UPDATE tasks
        SET assignee_user_id=?, assignee_role=NULL
        WHERE id=? AND status='pending'
        """,
        (assignee_user_id, task_id),
    )


def list_request_tasks(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT
          t.*,
          au.username AS assignee_username,
          du.username AS decided_by_username
        FROM tasks t
        LEFT JOIN users au ON au.id = t.assignee_user_id
        LEFT JOIN users du ON du.id = t.decided_by
        WHERE t.request_id = ?
        ORDER BY COALESCE(t.step_order, t.id) ASC
        """,
        (request_id,),
    ).fetchall()


def list_tasks_for_step(conn: sqlite3.Connection, request_id: int, step_order: int):
    return conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE request_id = ? AND step_order = ?
        ORDER BY id ASC
        """,
        (request_id, step_order),
    ).fetchall()


def cancel_pending_tasks_for_step(conn: sqlite3.Connection, request_id: int, step_order: int, *, except_task_id: int, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        """
        UPDATE tasks
        SET status='canceled', decided_by=?, decided_at=?, comment='canceled'
        WHERE request_id=? AND step_order=? AND status='pending' AND id<>?
        """,
        (decided_by, now, request_id, step_order, except_task_id),
    )


def create_resubmit_task(conn: sqlite3.Connection, request_id: int, owner_user_id: int) -> int:
    now = int(time.time())
    cur = conn.execute(
        """
        INSERT INTO tasks(request_id,step_order,step_key,assignee_user_id,assignee_role,status,created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (request_id, 0, "resubmit", owner_user_id, None, "pending", now),
    )
    return int(cur.lastrowid)


def cancel_all_pending_tasks(conn: sqlite3.Connection, request_id: int, *, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        """
        UPDATE tasks
        SET status='canceled', decided_by=?, decided_at=?, comment='canceled'
        WHERE request_id=? AND status='pending'
        """,
        (decided_by, now, request_id),
    )


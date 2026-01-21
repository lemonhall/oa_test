from __future__ import annotations

import sqlite3
import time


def create_request(
    conn: sqlite3.Connection,
    user_id: int,
    request_type: str,
    title: str,
    body: str,
    *,
    payload_json: str | None,
    workflow_key: str | None,
) -> int:
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO requests(user_id,request_type,workflow_key,title,body,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (user_id, request_type, workflow_key, title, body, "pending", now, now),
    )
    if payload_json is not None:
        conn.execute("UPDATE requests SET payload_json=? WHERE id=?", (payload_json, int(cur.lastrowid)))
    return int(cur.lastrowid)


def list_requests(conn: sqlite3.Connection, user_id: int, is_admin: bool):
    if is_admin:
        return conn.execute(
            """
            SELECT
              r.*,
              u.username AS owner_username,
              d.username AS decided_by_username,
              wf.name AS workflow_name,
              wf.category AS workflow_category,
              wf.scope_kind AS workflow_scope_kind,
              wf.scope_value AS workflow_scope_value,
              t.id AS pending_task_id,
              t.step_key AS pending_step_key,
              t.assignee_user_id AS pending_assignee_user_id,
              t.assignee_role AS pending_assignee_role,
              au.username AS pending_assignee_username
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN users d ON d.id = r.decided_by
            LEFT JOIN workflow_variants wf ON wf.workflow_key = r.workflow_key
            LEFT JOIN tasks t ON t.id = (
              SELECT id FROM tasks
              WHERE request_id = r.id AND status='pending'
              ORDER BY id DESC LIMIT 1
            )
            LEFT JOIN users au ON au.id = t.assignee_user_id
            ORDER BY r.id DESC
            """
        ).fetchall()

    return conn.execute(
        """
        SELECT
          r.*,
          u.username AS owner_username,
          d.username AS decided_by_username,
          wf.name AS workflow_name,
          wf.category AS workflow_category,
          wf.scope_kind AS workflow_scope_kind,
          wf.scope_value AS workflow_scope_value,
          t.id AS pending_task_id,
          t.step_key AS pending_step_key,
          t.assignee_user_id AS pending_assignee_user_id,
          t.assignee_role AS pending_assignee_role,
          au.username AS pending_assignee_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
        LEFT JOIN workflow_variants wf ON wf.workflow_key = r.workflow_key
        LEFT JOIN tasks t ON t.id = (
          SELECT id FROM tasks
          WHERE request_id = r.id AND status='pending'
          ORDER BY id DESC LIMIT 1
        )
        LEFT JOIN users au ON au.id = t.assignee_user_id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
        """,
        (user_id,),
    ).fetchall()


def get_request(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT
          r.*,
          u.username AS owner_username,
          d.username AS decided_by_username,
          wf.name AS workflow_name,
          wf.category AS workflow_category,
          wf.scope_kind AS workflow_scope_kind,
          wf.scope_value AS workflow_scope_value,
          t.id AS pending_task_id,
          t.step_key AS pending_step_key,
          t.assignee_user_id AS pending_assignee_user_id,
          t.assignee_role AS pending_assignee_role,
          au.username AS pending_assignee_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
        LEFT JOIN workflow_variants wf ON wf.workflow_key = r.workflow_key
        LEFT JOIN tasks t ON t.id = (
          SELECT id FROM tasks
          WHERE request_id = r.id AND status='pending'
          ORDER BY id DESC LIMIT 1
        )
        LEFT JOIN users au ON au.id = t.assignee_user_id
        WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()


def update_request_status(conn: sqlite3.Connection, request_id: int, *, status: str, decided_by: int | None) -> None:
    now = int(time.time())
    if status in {"approved", "rejected"} and decided_by is not None:
        conn.execute(
            "UPDATE requests SET status=?, decided_by=?, decided_at=?, updated_at=? WHERE id=?",
            (status, decided_by, now, now, request_id),
        )
    else:
        conn.execute("UPDATE requests SET status=?, updated_at=? WHERE id=?", (status, now, request_id))


def mark_request_changes_requested(conn: sqlite3.Connection, request_id: int) -> None:
    now = int(time.time())
    conn.execute(
        "UPDATE requests SET status=?, updated_at=? WHERE id=?",
        ("changes_requested", now, request_id),
    )


def reset_request_for_resubmit(conn: sqlite3.Connection, request_id: int, *, title: str, body: str, payload_json: str | None) -> None:
    now = int(time.time())
    conn.execute(
        """
        UPDATE requests
        SET title=?, body=?, payload_json=?, status='pending', decided_by=NULL, decided_at=NULL, updated_at=?
        WHERE id=?
        """,
        (title, body, payload_json, now, request_id),
    )


def decide_request(conn: sqlite3.Connection, request_id: int, status: str, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        "UPDATE requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, decided_by, now, request_id),
    )


from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .auth import hash_password


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column in _column_names(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requests (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL,
              decided_by INTEGER REFERENCES users(id),
              decided_at INTEGER,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
              step_key TEXT NOT NULL,
              assignee_user_id INTEGER REFERENCES users(id),
              assignee_role TEXT,
              status TEXT NOT NULL,
              decided_by INTEGER REFERENCES users(id),
              decided_at INTEGER,
              comment TEXT,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS request_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
              event_type TEXT NOT NULL,
              actor_user_id INTEGER REFERENCES users(id),
              message TEXT,
              created_at INTEGER NOT NULL
            );
            """
        )

        _ensure_column(conn, "users", "dept", "TEXT")
        _ensure_column(conn, "users", "manager_id", "INTEGER")
        _ensure_column(conn, "requests", "request_type", "TEXT NOT NULL DEFAULT 'generic'")
        _ensure_column(conn, "requests", "updated_at", "INTEGER")

        existing = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()["c"]
        if existing == 0:
            now = int(time.time())
            cur = conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("admin", hash_password("admin"), "admin", now),
            )
            admin_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at,manager_id) VALUES(?,?,?,?,?)",
                ("user", hash_password("user"), "user", now, admin_id),
            )
        else:
            # Best-effort: if the demo user exists and has no manager, point to an admin.
            admin = conn.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            if admin:
                conn.execute(
                    "UPDATE users SET manager_id=? WHERE username='user' AND (manager_id IS NULL OR manager_id='')",
                    (int(admin["id"]),),
                )


def get_user_by_username(conn: sqlite3.Connection, username: str):
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def get_user_by_id(conn: sqlite3.Connection, user_id: int):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT u.*, m.username AS manager_username
        FROM users u
        LEFT JOIN users m ON m.id = u.manager_id
        ORDER BY u.id ASC
        """
    ).fetchall()


_UNSET = object()


def update_user(conn: sqlite3.Connection, user_id: int, *, dept=_UNSET, manager_id=_UNSET) -> None:
    sets: list[str] = []
    params: list[object] = []
    if dept is not _UNSET:
        sets.append("dept = ?")
        params.append(dept)
    if manager_id is not _UNSET:
        sets.append("manager_id = ?")
        params.append(manager_id)
    if not sets:
        return
    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", tuple(params))


def create_session(conn: sqlite3.Connection, token: str, user_id: int, expires_at: int) -> None:
    conn.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, user_id, expires_at))


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_session_with_user(conn: sqlite3.Connection, token: str):
    return conn.execute(
        """
        SELECT s.token, s.expires_at, u.id AS user_id, u.username, u.role, u.dept, u.manager_id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()


def create_request(conn: sqlite3.Connection, user_id: int, request_type: str, title: str, body: str) -> int:
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO requests(user_id,request_type,title,body,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, request_type, title, body, "pending", now, now),
    )
    return int(cur.lastrowid)

def create_task(
    conn: sqlite3.Connection,
    request_id: int,
    *,
    step_key: str,
    assignee_user_id: int | None,
    assignee_role: str | None,
) -> int:
    now = int(time.time())
    cur = conn.execute(
        """
        INSERT INTO tasks(request_id,step_key,assignee_user_id,assignee_role,status,created_at)
        VALUES(?,?,?,?,?,?)
        """,
        (request_id, step_key, assignee_user_id, assignee_role, "pending", now),
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
          AND r.status='pending'
          AND (
            t.assignee_user_id = ?
            OR (t.assignee_role IS NOT NULL AND t.assignee_role = ?)
          )
        ORDER BY t.id DESC
        """,
        (user_id, role),
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
        ORDER BY t.id ASC
        """,
        (request_id,),
    ).fetchall()


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


def list_requests(conn: sqlite3.Connection, user_id: int, is_admin: bool):
    if is_admin:
        return conn.execute(
            """
            SELECT
              r.*,
              u.username AS owner_username,
              d.username AS decided_by_username,
              t.id AS pending_task_id,
              t.step_key AS pending_step_key,
              t.assignee_user_id AS pending_assignee_user_id,
              t.assignee_role AS pending_assignee_role,
              au.username AS pending_assignee_username
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN users d ON d.id = r.decided_by
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
          t.id AS pending_task_id,
          t.step_key AS pending_step_key,
          t.assignee_user_id AS pending_assignee_user_id,
          t.assignee_role AS pending_assignee_role,
          au.username AS pending_assignee_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
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
          t.id AS pending_task_id,
          t.step_key AS pending_step_key,
          t.assignee_user_id AS pending_assignee_user_id,
          t.assignee_role AS pending_assignee_role,
          au.username AS pending_assignee_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
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


def decide_request(conn: sqlite3.Connection, request_id: int, status: str, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        "UPDATE requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, decided_by, now, request_id),
    )

from __future__ import annotations

import sqlite3


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


def update_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    dept=_UNSET,
    manager_id=_UNSET,
    role=_UNSET,
    dept_id=_UNSET,
    position=_UNSET,
) -> None:
    sets: list[str] = []
    params: list[object] = []
    if dept is not _UNSET:
        sets.append("dept = ?")
        params.append(dept)
    if manager_id is not _UNSET:
        sets.append("manager_id = ?")
        params.append(manager_id)
    if role is not _UNSET:
        sets.append("role = ?")
        params.append(role)
    if dept_id is not _UNSET:
        sets.append("dept_id = ?")
        params.append(dept_id)
    if position is not _UNSET:
        sets.append("position = ?")
        params.append(position)
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
        SELECT s.*, u.username, u.role, u.dept, u.manager_id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()

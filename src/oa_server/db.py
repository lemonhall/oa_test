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
            """
        )

        existing = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()["c"]
        if existing == 0:
            now = int(time.time())
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("admin", hash_password("admin"), "admin", now),
            )
            conn.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                ("user", hash_password("user"), "user", now),
            )


def get_user_by_username(conn: sqlite3.Connection, username: str):
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_session(conn: sqlite3.Connection, token: str, user_id: int, expires_at: int) -> None:
    conn.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, user_id, expires_at))


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_session_with_user(conn: sqlite3.Connection, token: str):
    return conn.execute(
        """
        SELECT s.token, s.expires_at, u.id AS user_id, u.username, u.role
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()


def create_request(conn: sqlite3.Connection, user_id: int, title: str, body: str) -> int:
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO requests(user_id,title,body,status,created_at) VALUES(?,?,?,?,?)",
        (user_id, title, body, "pending", now),
    )
    return int(cur.lastrowid)


def list_requests(conn: sqlite3.Connection, user_id: int, is_admin: bool):
    if is_admin:
        return conn.execute(
            """
            SELECT r.*, u.username AS owner_username, d.username AS decided_by_username
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN users d ON d.id = r.decided_by
            ORDER BY r.id DESC
            """
        ).fetchall()

    return conn.execute(
        """
        SELECT r.*, u.username AS owner_username, d.username AS decided_by_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
        WHERE r.user_id = ?
        ORDER BY r.id DESC
        """,
        (user_id,),
    ).fetchall()


def get_request(conn: sqlite3.Connection, request_id: int):
    return conn.execute(
        """
        SELECT r.*, u.username AS owner_username, d.username AS decided_by_username
        FROM requests r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN users d ON d.id = r.decided_by
        WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()


def decide_request(conn: sqlite3.Connection, request_id: int, status: str, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        "UPDATE requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, decided_by, now, request_id),
    )

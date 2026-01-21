from __future__ import annotations

import sqlite3
import time


_DEFAULT_USER_PERMISSIONS = [
    "requests:create",
    "requests:read_own",
    "inbox:read",
    "notifications:read",
    "attachments:upload_own",
    "attachments:download_own",
]


def ensure_default_roles(conn: sqlite3.Connection) -> None:
    now = int(time.time())
    conn.execute("INSERT OR IGNORE INTO roles(name,created_at) VALUES(?,?)", ("admin", now))
    conn.execute("INSERT OR IGNORE INTO roles(name,created_at) VALUES(?,?)", ("user", now))

    existing = conn.execute(
        "SELECT COUNT(1) AS c FROM role_permissions WHERE role_name='user'",
    ).fetchone()["c"]
    if int(existing) == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO role_permissions(role_name,permission_key,created_at) VALUES(?,?,?)",
            [("user", p, now) for p in _DEFAULT_USER_PERMISSIONS],
        )


def upsert_role(conn: sqlite3.Connection, role_name: str) -> None:
    now = int(time.time())
    conn.execute("INSERT OR IGNORE INTO roles(name,created_at) VALUES(?,?)", (role_name, now))


def replace_role_permissions(conn: sqlite3.Connection, role_name: str, permissions: list[str]) -> None:
    now = int(time.time())
    conn.execute("DELETE FROM role_permissions WHERE role_name=?", (role_name,))
    conn.executemany(
        "INSERT OR IGNORE INTO role_permissions(role_name,permission_key,created_at) VALUES(?,?,?)",
        [(role_name, p, now) for p in permissions],
    )


def list_roles(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM roles ORDER BY name ASC").fetchall()


def list_role_permissions(conn: sqlite3.Connection, role_name: str) -> list[str]:
    rows = conn.execute(
        "SELECT permission_key FROM role_permissions WHERE role_name=? ORDER BY permission_key ASC",
        (role_name,),
    ).fetchall()
    return [str(r["permission_key"]) for r in rows]


def role_exists(conn: sqlite3.Connection, role_name: str) -> bool:
    row = conn.execute("SELECT 1 FROM roles WHERE name=? LIMIT 1", (role_name,)).fetchone()
    return row is not None


def role_has_permission(conn: sqlite3.Connection, role_name: str, permission_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM role_permissions WHERE role_name=? AND permission_key=? LIMIT 1",
        (role_name, permission_key),
    ).fetchone()
    return row is not None


from __future__ import annotations

import sqlite3
import time


def create_department(conn: sqlite3.Connection, *, name: str, parent_id: int | None) -> int:
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO departments(name,parent_id,created_at) VALUES(?,?,?)",
        (name, parent_id, now),
    )
    return int(cur.lastrowid)


def get_department(conn: sqlite3.Connection, dept_id: int):
    return conn.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()


def list_departments(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM departments ORDER BY id ASC").fetchall()


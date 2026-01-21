from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ..auth import hash_password
from .connection import connect
from .rbac import ensure_default_roles
from .workflows_legacy import ensure_default_workflows, migrate_workflows
from .workflow_variants import ensure_workflow_variants, migrate_workflow_variants


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

            CREATE TABLE IF NOT EXISTS request_watchers (
              request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              kind TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              UNIQUE(request_id, user_id, kind)
            );

            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              request_id INTEGER REFERENCES requests(id) ON DELETE CASCADE,
              event_type TEXT NOT NULL,
              actor_user_id INTEGER REFERENCES users(id),
              message TEXT,
              created_at INTEGER NOT NULL,
              read_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS attachments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
              uploader_user_id INTEGER NOT NULL REFERENCES users(id),
              filename TEXT NOT NULL,
              content_type TEXT,
              size INTEGER NOT NULL,
              storage_path TEXT NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS roles (
              name TEXT PRIMARY KEY,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS role_permissions (
              role_name TEXT NOT NULL REFERENCES roles(name) ON DELETE CASCADE,
              permission_key TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              UNIQUE(role_name, permission_key)
            );

            CREATE TABLE IF NOT EXISTS delegations (
              delegator_user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              delegate_user_id INTEGER REFERENCES users(id),
              active INTEGER NOT NULL,
              created_at INTEGER NOT NULL,
              revoked_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS departments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              parent_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_definitions (
              request_type TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              enabled INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_steps (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_type TEXT NOT NULL REFERENCES workflow_definitions(request_type) ON DELETE CASCADE,
              step_order INTEGER NOT NULL,
              step_key TEXT NOT NULL,
              assignee_kind TEXT NOT NULL,
              assignee_value TEXT,
              condition_kind TEXT,
              condition_value TEXT,
              created_at INTEGER NOT NULL,
              UNIQUE(request_type, step_order)
            );

            -- Workflow catalog v2: supports grouping + multiple variants per request_type (e.g. dept-specific).
            CREATE TABLE IF NOT EXISTS workflow_variants (
              workflow_key TEXT PRIMARY KEY,
              request_type TEXT NOT NULL,
              name TEXT NOT NULL,
              category TEXT NOT NULL,
              scope_kind TEXT NOT NULL,
              scope_value TEXT,
              enabled INTEGER NOT NULL,
              is_default INTEGER NOT NULL,
              created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflow_variant_steps (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              workflow_key TEXT NOT NULL REFERENCES workflow_variants(workflow_key) ON DELETE CASCADE,
              step_order INTEGER NOT NULL,
              step_key TEXT NOT NULL,
              assignee_kind TEXT NOT NULL,
              assignee_value TEXT,
              condition_kind TEXT,
              condition_value TEXT,
              created_at INTEGER NOT NULL,
              UNIQUE(workflow_key, step_order)
            );
            """
        )

        _ensure_column(conn, "users", "dept", "TEXT")
        _ensure_column(conn, "users", "manager_id", "INTEGER")
        _ensure_column(conn, "users", "dept_id", "INTEGER")
        _ensure_column(conn, "users", "position", "TEXT")
        _ensure_column(conn, "requests", "request_type", "TEXT NOT NULL DEFAULT 'generic'")
        _ensure_column(conn, "requests", "workflow_key", "TEXT")
        _ensure_column(conn, "requests", "payload_json", "TEXT")
        _ensure_column(conn, "requests", "updated_at", "INTEGER")
        _ensure_column(conn, "tasks", "step_order", "INTEGER")
        _ensure_column(conn, "workflow_steps", "condition_kind", "TEXT")
        _ensure_column(conn, "workflow_steps", "condition_value", "TEXT")

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
            admin = conn.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            if admin:
                conn.execute(
                    "UPDATE users SET manager_id=? WHERE username='user' AND (manager_id IS NULL OR manager_id='')",
                    (int(admin["id"]),),
                )

        ensure_default_workflows(conn)
        migrate_workflows(conn)
        ensure_workflow_variants(conn)
        migrate_workflow_variants(conn)
        ensure_default_roles(conn)


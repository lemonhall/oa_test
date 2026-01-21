from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .auth import hash_password


def _connect_raw(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = _connect_raw(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
            # Best-effort: if the demo user exists and has no manager, point to an admin.
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


def ensure_default_workflows(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(1) AS c FROM workflow_definitions").fetchone()["c"]
    if int(existing) > 0:
        return

    now = int(time.time())
    conn.execute(
        "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
        ("leave", "Leave Request", 1, now),
    )
    conn.execute(
        "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
        ("expense", "Expense Reimbursement", 1, now),
    )
    conn.execute(
        "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
        ("generic", "Generic Request", 1, now),
    )
    conn.execute(
        "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
        ("purchase", "Purchase Request", 1, now),
    )

    conn.executemany(
        """
        INSERT INTO workflow_steps(request_type,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        [
            ("leave", 1, "manager", "manager", None, None, None, now),
            ("expense", 1, "manager", "manager", None, None, None, now),
            ("expense", 2, "gm", "role", "admin", "min_amount", "5000", now),
            ("expense", 3, "finance", "role", "admin", None, None, now),
            ("generic", 1, "admin", "role", "admin", None, None, now),
            ("purchase", 1, "manager", "manager", None, None, None, now),
            ("purchase", 2, "gm", "role", "admin", "min_amount", "20000", now),
            ("purchase", 3, "procurement", "role", "admin", None, None, now),
            ("purchase", 4, "finance", "role", "admin", None, None, now),
        ],
    )


def migrate_workflows(conn: sqlite3.Connection) -> None:
    # Narrow migration: upgrade legacy expense flow (manager -> finance) to support a GM threshold step:
    # manager -> gm(min_amount=5000) -> finance
    steps = conn.execute(
        "SELECT step_order, step_key, condition_kind FROM workflow_steps WHERE request_type=? ORDER BY step_order ASC",
        ("expense",),
    ).fetchall()
    if not steps:
        return
    step_keys = [str(s["step_key"]) for s in steps]
    if "gm" in step_keys:
        return
    if step_keys != ["manager", "finance"]:
        return
    if any(s["condition_kind"] is not None for s in steps):
        return

    now = int(time.time())
    conn.execute(
        "UPDATE workflow_steps SET step_order=3 WHERE request_type=? AND step_order=2 AND step_key='finance'",
        ("expense",),
    )
    conn.execute(
        """
        INSERT INTO workflow_steps(
          request_type,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
        )
        VALUES(?,?,?,?,?,?,?,?)
        """,
        ("expense", 2, "gm", "role", "admin", "min_amount", "5000", now),
    )

    # Ensure purchase workflow exists for older DBs.
    has_purchase = conn.execute(
        "SELECT 1 FROM workflow_definitions WHERE request_type=? LIMIT 1",
        ("purchase",),
    ).fetchone()
    if not has_purchase:
        conn.execute(
            "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
            ("purchase", "Purchase Request", 1, now),
        )
        conn.executemany(
            """
            INSERT INTO workflow_steps(
              request_type,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                ("purchase", 1, "manager", "manager", None, None, None, now),
                ("purchase", 2, "gm", "role", "admin", "min_amount", "20000", now),
                ("purchase", 3, "procurement", "role", "admin", None, None, now),
                ("purchase", 4, "finance", "role", "admin", None, None, now),
            ],
        )


def _default_category_for_request_type(request_type: str) -> str:
    if request_type in {"leave"}:
        return "HR"
    if request_type in {"expense"}:
        return "Finance"
    if request_type in {"purchase"}:
        return "Procurement"
    return "General"


def ensure_workflow_variants(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(1) AS c FROM workflow_variants").fetchone()["c"]
    if int(existing) > 0:
        return

    legacy_defs = conn.execute("SELECT * FROM workflow_definitions ORDER BY request_type ASC").fetchall()
    legacy_steps = conn.execute("SELECT * FROM workflow_steps ORDER BY request_type ASC, step_order ASC").fetchall()
    if not legacy_defs:
        return

    steps_by_type: dict[str, list[sqlite3.Row]] = {}
    for s in legacy_steps:
        steps_by_type.setdefault(str(s["request_type"]), []).append(s)

    for d in legacy_defs:
        request_type = str(d["request_type"])
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO workflow_variants(
              workflow_key,request_type,name,category,scope_kind,scope_value,enabled,is_default,created_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                request_type,
                request_type,
                str(d["name"]),
                _default_category_for_request_type(request_type),
                "global",
                None,
                int(d["enabled"]),
                1,
                now,
            ),
        )

        for s in steps_by_type.get(request_type, []):
            conn.execute(
                """
                INSERT INTO workflow_variant_steps(
                  workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    request_type,
                    int(s["step_order"]),
                    str(s["step_key"]),
                    str(s["assignee_kind"]),
                    None if s["assignee_value"] is None else str(s["assignee_value"]),
                    None if s["condition_kind"] is None else str(s["condition_kind"]),
                    None if s["condition_value"] is None else str(s["condition_value"]),
                    now,
                ),
            )


def migrate_workflow_variants(conn: sqlite3.Connection) -> None:
    # Mirror key legacy migrations for v2 catalog, for existing DBs that were created before v2.
    steps = conn.execute(
        "SELECT step_order, step_key, condition_kind FROM workflow_variant_steps WHERE workflow_key=? ORDER BY step_order ASC",
        ("expense",),
    ).fetchall()
    if steps:
        step_keys = [str(s["step_key"]) for s in steps]
        if "gm" not in step_keys and step_keys == ["manager", "finance"]:
            now = int(time.time())
            conn.execute(
                "UPDATE workflow_variant_steps SET step_order=3 WHERE workflow_key=? AND step_order=2 AND step_key='finance'",
                ("expense",),
            )
            conn.execute(
                """
                INSERT INTO workflow_variant_steps(
                  workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                ("expense", 2, "gm", "role", "admin", "min_amount", "5000", now),
            )

    has_purchase = conn.execute("SELECT 1 FROM workflow_variants WHERE workflow_key=? LIMIT 1", ("purchase",)).fetchone()
    if not has_purchase:
        now = int(time.time())
        conn.execute(
            """
            INSERT INTO workflow_variants(
              workflow_key,request_type,name,category,scope_kind,scope_value,enabled,is_default,created_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            ("purchase", "purchase", "Purchase Request", "Procurement", "global", None, 1, 1, now),
        )
        conn.executemany(
            """
            INSERT INTO workflow_variant_steps(
              workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                ("purchase", 1, "manager", "manager", None, None, None, now),
                ("purchase", 2, "gm", "role", "admin", "min_amount", "20000", now),
                ("purchase", 3, "procurement", "role", "admin", None, None, now),
                ("purchase", 4, "finance", "role", "admin", None, None, now),
            ],
        )


def list_workflows(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM workflow_definitions ORDER BY request_type ASC").fetchall()


def list_workflow_steps(conn: sqlite3.Connection, request_type: str):
    return conn.execute(
        "SELECT * FROM workflow_steps WHERE request_type = ? ORDER BY step_order ASC",
        (request_type,),
    ).fetchall()


def replace_workflow_steps(conn: sqlite3.Connection, request_type: str, *, name: str | None, enabled: bool, steps: list[dict]):
    now = int(time.time())
    # Legacy table update (kept for backward compatibility).
    conn.execute(
        """
        INSERT INTO workflow_definitions(request_type,name,enabled,created_at)
        VALUES(?,?,?,?)
        ON CONFLICT(request_type) DO UPDATE SET name=excluded.name, enabled=excluded.enabled
        """,
        (request_type, name or request_type, 1 if enabled else 0, now),
    )
    conn.execute("DELETE FROM workflow_steps WHERE request_type = ?", (request_type,))
    for s in steps:
        conn.execute(
            """
            INSERT INTO workflow_steps(
              request_type,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                request_type,
                int(s["step_order"]),
                str(s["step_key"]),
                str(s["assignee_kind"]),
                None if s.get("assignee_value") is None else str(s["assignee_value"]),
                None if s.get("condition_kind") is None else str(s.get("condition_kind")),
                None if s.get("condition_value") is None else str(s.get("condition_value")),
                now,
            ),
        )

    # v2 catalog update (global default workflow with key=request_type).
    conn.execute(
        """
        INSERT INTO workflow_variants(
          workflow_key,request_type,name,category,scope_kind,scope_value,enabled,is_default,created_at
        )
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(workflow_key) DO UPDATE SET
          request_type=excluded.request_type,
          name=excluded.name,
          category=excluded.category,
          scope_kind=excluded.scope_kind,
          scope_value=excluded.scope_value,
          enabled=excluded.enabled,
          is_default=excluded.is_default
        """,
        (
            request_type,
            request_type,
            name or request_type,
            _default_category_for_request_type(request_type),
            "global",
            None,
            1 if enabled else 0,
            1,
            now,
        ),
    )
    conn.execute("DELETE FROM workflow_variant_steps WHERE workflow_key = ?", (request_type,))
    for s in steps:
        conn.execute(
            """
            INSERT INTO workflow_variant_steps(
              workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                request_type,
                int(s["step_order"]),
                str(s["step_key"]),
                str(s["assignee_kind"]),
                None if s.get("assignee_value") is None else str(s["assignee_value"]),
                None if s.get("condition_kind") is None else str(s.get("condition_kind")),
                None if s.get("condition_value") is None else str(s.get("condition_value")),
                now,
            ),
        )


def get_workflow_variant(conn: sqlite3.Connection, workflow_key: str):
    return conn.execute("SELECT * FROM workflow_variants WHERE workflow_key = ?", (workflow_key,)).fetchone()


def list_available_workflow_variants(conn: sqlite3.Connection, *, dept: str | None):
    if dept:
        return conn.execute(
            """
            SELECT * FROM workflow_variants
            WHERE enabled=1 AND (scope_kind='global' OR (scope_kind='dept' AND scope_value=?))
            ORDER BY category ASC, name ASC
            """,
            (dept,),
        ).fetchall()
    return conn.execute(
        """
        SELECT * FROM workflow_variants
        WHERE enabled=1 AND scope_kind='global'
        ORDER BY category ASC, name ASC
        """
    ).fetchall()


def upsert_workflow_variant(
    conn: sqlite3.Connection,
    *,
    workflow_key: str,
    request_type: str,
    name: str,
    category: str,
    scope_kind: str,
    scope_value: str | None,
    enabled: bool,
    is_default: bool,
) -> None:
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO workflow_variants(
          workflow_key,request_type,name,category,scope_kind,scope_value,enabled,is_default,created_at
        )
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(workflow_key) DO UPDATE SET
          request_type=excluded.request_type,
          name=excluded.name,
          category=excluded.category,
          scope_kind=excluded.scope_kind,
          scope_value=excluded.scope_value,
          enabled=excluded.enabled,
          is_default=excluded.is_default
        """,
        (
            workflow_key,
            request_type,
            name,
            category,
            scope_kind,
            scope_value,
            1 if enabled else 0,
            1 if is_default else 0,
            now,
        ),
    )

    if is_default:
        if scope_kind == "dept":
            conn.execute(
                """
                UPDATE workflow_variants
                SET is_default=0
                WHERE request_type=? AND scope_kind='dept' AND scope_value=? AND workflow_key<>?
                """,
                (request_type, scope_value, workflow_key),
            )
        elif scope_kind == "global":
            conn.execute(
                """
                UPDATE workflow_variants
                SET is_default=0
                WHERE request_type=? AND scope_kind='global' AND workflow_key<>?
                """,
                (request_type, workflow_key),
            )


def replace_workflow_variant_steps(conn: sqlite3.Connection, workflow_key: str, steps: list[dict]) -> None:
    now = int(time.time())
    conn.execute("DELETE FROM workflow_variant_steps WHERE workflow_key = ?", (workflow_key,))
    for s in steps:
        conn.execute(
            """
            INSERT INTO workflow_variant_steps(
              workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                workflow_key,
                int(s["step_order"]),
                str(s["step_key"]),
                str(s["assignee_kind"]),
                None if s.get("assignee_value") is None else str(s.get("assignee_value")),
                None if s.get("condition_kind") is None else str(s.get("condition_kind")),
                None if s.get("condition_value") is None else str(s.get("condition_value")),
                now,
            ),
        )


def delete_workflow_variant(conn: sqlite3.Connection, workflow_key: str) -> None:
    conn.execute("DELETE FROM workflow_variants WHERE workflow_key = ?", (workflow_key,))


def list_workflow_variants_admin(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM workflow_variants ORDER BY category ASC, name ASC").fetchall()


def resolve_default_workflow_key(conn: sqlite3.Connection, request_type: str, *, dept: str | None) -> str | None:
    if dept:
        row = conn.execute(
            """
            SELECT workflow_key FROM workflow_variants
            WHERE request_type=? AND enabled=1 AND is_default=1 AND scope_kind='dept' AND scope_value=?
            LIMIT 1
            """,
            (request_type, dept),
        ).fetchone()
        if row:
            return str(row["workflow_key"])
    row = conn.execute(
        """
        SELECT workflow_key FROM workflow_variants
        WHERE request_type=? AND enabled=1 AND is_default=1 AND scope_kind='global'
        LIMIT 1
        """,
        (request_type,),
    ).fetchone()
    return None if not row else str(row["workflow_key"])


def list_workflow_variant_steps(conn: sqlite3.Connection, workflow_key: str):
    return conn.execute(
        "SELECT * FROM workflow_variant_steps WHERE workflow_key = ? ORDER BY step_order ASC",
        (workflow_key,),
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


def decide_request(conn: sqlite3.Connection, request_id: int, status: str, decided_by: int) -> None:
    now = int(time.time())
    conn.execute(
        "UPDATE requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
        (status, decided_by, now, request_id),
    )

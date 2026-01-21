from __future__ import annotations

import sqlite3
import time


def _default_category_for_request_type(request_type: str) -> str:
    if request_type in {
        "leave",
        "overtime",
        "attendance_correction",
        "business_trip",
        "outing",
        "onboarding",
        "probation",
        "resignation",
        "job_transfer",
        "salary_adjustment",
    }:
        return "HR/Admin"
    if request_type in {"expense", "loan", "payment", "budget", "invoice", "fixed_asset_accounting"}:
        return "Finance"
    if request_type in {"travel_expense"}:
        return "Finance"
    if request_type in {"purchase", "purchase_plus", "quote_compare", "acceptance", "inventory_in", "inventory_out"}:
        return "Procurement"
    if request_type in {"device_claim", "asset_transfer", "asset_maintenance", "asset_scrap"}:
        return "Assets"
    if request_type in {"contract", "legal_review", "seal", "archive"}:
        return "Contract/Legal"
    if request_type in {"account_open", "permission", "vpn_email", "it_device"}:
        return "IT"
    if request_type in {"meeting_room", "car", "supplies"}:
        return "Logistics"
    if request_type in {"policy_announcement", "read_ack"}:
        return "Policy/Compliance"
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

    def _ensure_variant_workflow(workflow_key: str, request_type: str, name: str, steps: list[tuple[int, str, str, str | None]]) -> None:
        has = conn.execute("SELECT 1 FROM workflow_variants WHERE workflow_key=? LIMIT 1", (workflow_key,)).fetchone()
        now = int(time.time())
        if not has:
            conn.execute(
                """
                INSERT INTO workflow_variants(
                  workflow_key,request_type,name,category,scope_kind,scope_value,enabled,is_default,created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    workflow_key,
                    request_type,
                    name,
                    _default_category_for_request_type(request_type),
                    "global",
                    None,
                    1,
                    1,
                    now,
                ),
            )
        has_steps = conn.execute("SELECT 1 FROM workflow_variant_steps WHERE workflow_key=? LIMIT 1", (workflow_key,)).fetchone()
        if has_steps:
            return
        conn.executemany(
            """
            INSERT INTO workflow_variant_steps(
              workflow_key,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            [(workflow_key, order, step_key, assignee_kind, assignee_value, None, None, now) for order, step_key, assignee_kind, assignee_value in steps],
        )

    # Ensure HR/Admin workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("overtime", "加班申请", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("attendance_correction", "补卡/改卡申请", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("business_trip", "出差申请", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("outing", "外出申请", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("travel_expense", "差旅报销", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
        ("onboarding", "入职流程", [(1, "hr", "role", "admin"), (2, "admin", "role", "admin")]),
        ("probation", "转正流程", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("resignation", "离职流程", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("job_transfer", "调岗流程", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
        ("salary_adjustment", "调薪流程", [(1, "manager", "manager", None), (2, "hr", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure Finance workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("loan", "借款申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
        ("payment", "付款申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "gm", "role", "admin"), (4, "admin", "role", "admin")]),
        ("budget", "预算占用/预支", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "gm", "role", "admin"), (4, "admin", "role", "admin")]),
        ("invoice", "发票/开票申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
        ("fixed_asset_accounting", "固定资产入账审批", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure Procurement/Assets workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("purchase_plus", "采购（增强版）", [(1, "manager", "manager", None), (2, "procurement", "role", "admin"), (3, "gm", "role", "admin"), (4, "finance", "role", "admin"), (5, "admin", "role", "admin")]),
        ("quote_compare", "比价/询价记录", [(1, "manager", "manager", None), (2, "procurement", "role", "admin"), (3, "finance", "role", "admin"), (4, "admin", "role", "admin")]),
        ("acceptance", "验收流程", [(1, "manager", "manager", None), (2, "procurement", "role", "admin"), (3, "admin", "role", "admin")]),
        ("inventory_in", "入库", [(1, "manager", "manager", None), (2, "procurement", "role", "admin"), (3, "admin", "role", "admin")]),
        ("inventory_out", "出库", [(1, "manager", "manager", None), (2, "procurement", "role", "admin"), (3, "admin", "role", "admin")]),
        ("device_claim", "设备申领", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
        ("asset_transfer", "资产调拨", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
        ("asset_maintenance", "资产维修", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
        ("asset_scrap", "资产报废", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure Contract/Legal workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("contract", "Contract Approval", [(1, "manager", "manager", None), (2, "legal", "role", "admin"), (3, "admin", "role", "admin")]),
        ("legal_review", "Legal Review", [(1, "legal", "role", "admin"), (2, "admin", "role", "admin")]),
        ("seal", "Seal Application", [(1, "legal", "role", "admin"), (2, "admin", "role", "admin")]),
        ("archive", "Archive", [(1, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure IT/Access workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("account_open", "Account Open", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
        ("permission", "Access Request", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
        ("vpn_email", "VPN/Email Open", [(1, "it", "role", "admin"), (2, "admin", "role", "admin")]),
        ("it_device", "IT Device Request", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure Logistics workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("meeting_room", "Meeting Room Booking", [(1, "admin", "role", "admin")]),
        ("car", "Car Request", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
        ("supplies", "Supplies Request", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)

    # Ensure Policy/Compliance workflows exist in v2 catalog for existing DBs.
    for rt, name, steps in [
        ("policy_announcement", "Policy Announcement", [(1, "admin", "role", "admin")]),
        ("read_ack", "Read Acknowledgement", [(1, "ack", "users_all", "all")]),
    ]:
        _ensure_variant_workflow(rt, rt, name, steps)


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


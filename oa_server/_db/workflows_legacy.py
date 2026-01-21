from __future__ import annotations

import sqlite3
import time


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
    for rt, name in [
        ("overtime", "加班申请"),
        ("attendance_correction", "补卡/改卡申请"),
        ("business_trip", "出差申请"),
        ("outing", "外出申请"),
        ("travel_expense", "差旅报销"),
        ("onboarding", "入职流程"),
        ("probation", "转正流程"),
        ("resignation", "离职流程"),
        ("job_transfer", "调岗流程"),
        ("salary_adjustment", "调薪流程"),
        ("loan", "借款申请"),
        ("payment", "付款申请"),
        ("budget", "预算占用/预支"),
        ("invoice", "发票/开票申请"),
        ("fixed_asset_accounting", "固定资产入账审批"),
        ("purchase_plus", "采购（增强版）"),
        ("quote_compare", "比价/询价记录"),
        ("acceptance", "验收流程"),
        ("inventory_in", "入库"),
        ("inventory_out", "出库"),
        ("device_claim", "设备申领"),
        ("asset_transfer", "资产调拨"),
        ("asset_maintenance", "资产维修"),
        ("asset_scrap", "资产报废"),
        ("contract", "Contract Approval"),
        ("legal_review", "Legal Review"),
        ("seal", "Seal Application"),
        ("archive", "Archive"),
        ("account_open", "Account Open"),
        ("permission", "Access Request"),
        ("vpn_email", "VPN/Email Open"),
        ("it_device", "IT Device Request"),
        ("meeting_room", "Meeting Room Booking"),
        ("car", "Car Request"),
        ("supplies", "Supplies Request"),
        ("policy_announcement", "Policy Announcement"),
        ("read_ack", "Read Acknowledgement"),
    ]:
        conn.execute(
            "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
            (rt, name, 1, now),
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
            ("overtime", 1, "manager", "manager", None, None, None, now),
            ("overtime", 2, "hr", "role", "admin", None, None, now),
            ("overtime", 3, "admin", "role", "admin", None, None, now),
            ("attendance_correction", 1, "manager", "manager", None, None, None, now),
            ("attendance_correction", 2, "hr", "role", "admin", None, None, now),
            ("attendance_correction", 3, "admin", "role", "admin", None, None, now),
            ("business_trip", 1, "manager", "manager", None, None, None, now),
            ("business_trip", 2, "hr", "role", "admin", None, None, now),
            ("business_trip", 3, "admin", "role", "admin", None, None, now),
            ("outing", 1, "manager", "manager", None, None, None, now),
            ("outing", 2, "hr", "role", "admin", None, None, now),
            ("outing", 3, "admin", "role", "admin", None, None, now),
            ("travel_expense", 1, "manager", "manager", None, None, None, now),
            ("travel_expense", 2, "finance", "role", "admin", None, None, now),
            ("travel_expense", 3, "admin", "role", "admin", None, None, now),
            ("onboarding", 1, "hr", "role", "admin", None, None, now),
            ("onboarding", 2, "admin", "role", "admin", None, None, now),
            ("probation", 1, "manager", "manager", None, None, None, now),
            ("probation", 2, "hr", "role", "admin", None, None, now),
            ("probation", 3, "admin", "role", "admin", None, None, now),
            ("resignation", 1, "manager", "manager", None, None, None, now),
            ("resignation", 2, "hr", "role", "admin", None, None, now),
            ("resignation", 3, "admin", "role", "admin", None, None, now),
            ("job_transfer", 1, "manager", "manager", None, None, None, now),
            ("job_transfer", 2, "hr", "role", "admin", None, None, now),
            ("job_transfer", 3, "admin", "role", "admin", None, None, now),
            ("salary_adjustment", 1, "manager", "manager", None, None, None, now),
            ("salary_adjustment", 2, "hr", "role", "admin", None, None, now),
            ("salary_adjustment", 3, "admin", "role", "admin", None, None, now),
            ("loan", 1, "manager", "manager", None, None, None, now),
            ("loan", 2, "finance", "role", "admin", None, None, now),
            ("loan", 3, "admin", "role", "admin", None, None, now),
            ("payment", 1, "manager", "manager", None, None, None, now),
            ("payment", 2, "finance", "role", "admin", None, None, now),
            ("payment", 3, "gm", "role", "admin", "min_amount", "20000", now),
            ("payment", 4, "admin", "role", "admin", None, None, now),
            ("budget", 1, "manager", "manager", None, None, None, now),
            ("budget", 2, "finance", "role", "admin", None, None, now),
            ("budget", 3, "gm", "role", "admin", "min_amount", "50000", now),
            ("budget", 4, "admin", "role", "admin", None, None, now),
            ("invoice", 1, "manager", "manager", None, None, None, now),
            ("invoice", 2, "finance", "role", "admin", None, None, now),
            ("invoice", 3, "admin", "role", "admin", None, None, now),
            ("fixed_asset_accounting", 1, "manager", "manager", None, None, None, now),
            ("fixed_asset_accounting", 2, "finance", "role", "admin", None, None, now),
            ("fixed_asset_accounting", 3, "admin", "role", "admin", None, None, now),
            ("purchase_plus", 1, "manager", "manager", None, None, None, now),
            ("purchase_plus", 2, "procurement", "role", "admin", None, None, now),
            ("purchase_plus", 3, "gm", "role", "admin", None, None, now),
            ("purchase_plus", 4, "finance", "role", "admin", None, None, now),
            ("purchase_plus", 5, "admin", "role", "admin", None, None, now),
            ("quote_compare", 1, "manager", "manager", None, None, None, now),
            ("quote_compare", 2, "procurement", "role", "admin", None, None, now),
            ("quote_compare", 3, "finance", "role", "admin", None, None, now),
            ("quote_compare", 4, "admin", "role", "admin", None, None, now),
            ("acceptance", 1, "manager", "manager", None, None, None, now),
            ("acceptance", 2, "procurement", "role", "admin", None, None, now),
            ("acceptance", 3, "admin", "role", "admin", None, None, now),
            ("inventory_in", 1, "manager", "manager", None, None, None, now),
            ("inventory_in", 2, "procurement", "role", "admin", None, None, now),
            ("inventory_in", 3, "admin", "role", "admin", None, None, now),
            ("inventory_out", 1, "manager", "manager", None, None, None, now),
            ("inventory_out", 2, "procurement", "role", "admin", None, None, now),
            ("inventory_out", 3, "admin", "role", "admin", None, None, now),
            ("device_claim", 1, "manager", "manager", None, None, None, now),
            ("device_claim", 2, "admin", "role", "admin", None, None, now),
            ("asset_transfer", 1, "manager", "manager", None, None, None, now),
            ("asset_transfer", 2, "admin", "role", "admin", None, None, now),
            ("asset_maintenance", 1, "manager", "manager", None, None, None, now),
            ("asset_maintenance", 2, "admin", "role", "admin", None, None, now),
            ("asset_scrap", 1, "manager", "manager", None, None, None, now),
            ("asset_scrap", 2, "finance", "role", "admin", None, None, now),
            ("asset_scrap", 3, "admin", "role", "admin", None, None, now),
            ("contract", 1, "manager", "manager", None, None, None, now),
            ("contract", 2, "legal", "role", "admin", None, None, now),
            ("contract", 3, "admin", "role", "admin", None, None, now),
            ("legal_review", 1, "legal", "role", "admin", None, None, now),
            ("legal_review", 2, "admin", "role", "admin", None, None, now),
            ("seal", 1, "legal", "role", "admin", None, None, now),
            ("seal", 2, "admin", "role", "admin", None, None, now),
            ("archive", 1, "admin", "role", "admin", None, None, now),
            ("account_open", 1, "manager", "manager", None, None, None, now),
            ("account_open", 2, "it", "role", "admin", None, None, now),
            ("account_open", 3, "admin", "role", "admin", None, None, now),
            ("permission", 1, "manager", "manager", None, None, None, now),
            ("permission", 2, "it", "role", "admin", None, None, now),
            ("permission", 3, "admin", "role", "admin", None, None, now),
            ("vpn_email", 1, "it", "role", "admin", None, None, now),
            ("vpn_email", 2, "admin", "role", "admin", None, None, now),
            ("it_device", 1, "manager", "manager", None, None, None, now),
            ("it_device", 2, "it", "role", "admin", None, None, now),
            ("it_device", 3, "admin", "role", "admin", None, None, now),
            ("meeting_room", 1, "admin", "role", "admin", None, None, now),
            ("car", 1, "manager", "manager", None, None, None, now),
            ("car", 2, "admin", "role", "admin", None, None, now),
            ("supplies", 1, "manager", "manager", None, None, None, now),
            ("supplies", 2, "admin", "role", "admin", None, None, now),
            ("policy_announcement", 1, "admin", "role", "admin", None, None, now),
            ("read_ack", 1, "ack", "users_all", "all", None, None, now),
        ],
    )


def migrate_workflows(conn: sqlite3.Connection) -> None:
    # Narrow migration: upgrade legacy expense flow (manager -> finance) to support a GM threshold step:
    # manager -> gm(min_amount=5000) -> finance
    now = int(time.time())

    steps = conn.execute(
        "SELECT step_order, step_key, condition_kind FROM workflow_steps WHERE request_type=? ORDER BY step_order ASC",
        ("expense",),
    ).fetchall()
    if steps:
        step_keys = [str(s["step_key"]) for s in steps]
        if "gm" not in step_keys and step_keys == ["manager", "finance"] and not any(s["condition_kind"] is not None for s in steps):
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

    def _ensure_legacy_workflow(request_type: str, name: str, steps: list[tuple[int, str, str, str | None]]) -> None:
        has_def = conn.execute(
            "SELECT 1 FROM workflow_definitions WHERE request_type=? LIMIT 1",
            (request_type,),
        ).fetchone()
        if not has_def:
            conn.execute(
                "INSERT INTO workflow_definitions(request_type,name,enabled,created_at) VALUES(?,?,?,?)",
                (request_type, name, 1, now),
            )

        has_steps = conn.execute("SELECT 1 FROM workflow_steps WHERE request_type=? LIMIT 1", (request_type,)).fetchone()
        if has_steps:
            return
        conn.executemany(
            """
            INSERT INTO workflow_steps(
              request_type,step_order,step_key,assignee_kind,assignee_value,condition_kind,condition_value,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            [(request_type, order, step_key, assignee_kind, assignee_value, None, None, now) for order, step_key, assignee_kind, assignee_value in steps],
        )

    # Ensure HR/Admin workflow catalog exists for older DBs.
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
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure Finance workflow catalog exists for older DBs.
    for rt, name, steps in [
        ("loan", "借款申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
        ("payment", "付款申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "gm", "role", "admin"), (4, "admin", "role", "admin")]),
        ("budget", "预算占用/预支", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "gm", "role", "admin"), (4, "admin", "role", "admin")]),
        ("invoice", "发票/开票申请", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
        ("fixed_asset_accounting", "固定资产入账审批", [(1, "manager", "manager", None), (2, "finance", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure Procurement/Assets workflow catalog exists for older DBs.
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
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure Contract/Legal workflow catalog exists for older DBs.
    for rt, name, steps in [
        ("contract", "Contract Approval", [(1, "manager", "manager", None), (2, "legal", "role", "admin"), (3, "admin", "role", "admin")]),
        ("legal_review", "Legal Review", [(1, "legal", "role", "admin"), (2, "admin", "role", "admin")]),
        ("seal", "Seal Application", [(1, "legal", "role", "admin"), (2, "admin", "role", "admin")]),
        ("archive", "Archive", [(1, "admin", "role", "admin")]),
    ]:
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure IT/Access workflow catalog exists for older DBs.
    for rt, name, steps in [
        ("account_open", "Account Open", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
        ("permission", "Access Request", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
        ("vpn_email", "VPN/Email Open", [(1, "it", "role", "admin"), (2, "admin", "role", "admin")]),
        ("it_device", "IT Device Request", [(1, "manager", "manager", None), (2, "it", "role", "admin"), (3, "admin", "role", "admin")]),
    ]:
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure Logistics workflow catalog exists for older DBs.
    for rt, name, steps in [
        ("meeting_room", "Meeting Room Booking", [(1, "admin", "role", "admin")]),
        ("car", "Car Request", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
        ("supplies", "Supplies Request", [(1, "manager", "manager", None), (2, "admin", "role", "admin")]),
    ]:
        _ensure_legacy_workflow(rt, name, steps)

    # Ensure Policy/Compliance workflow catalog exists for older DBs.
    for rt, name, steps in [
        ("policy_announcement", "Policy Announcement", [(1, "admin", "role", "admin")]),
        ("read_ack", "Read Acknowledgement", [(1, "ack", "users_all", "all")]),
    ]:
        _ensure_legacy_workflow(rt, name, steps)


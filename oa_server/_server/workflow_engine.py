from __future__ import annotations

from . import workflow_conditions
from .. import db
from ..auth import AuthenticatedUser


def create_initial_task(
    conn,
    request_id: int,
    *,
    creator: AuthenticatedUser,
    request_type: str,
    workflow_key: str | None,
) -> None:
    wk = workflow_key
    if not wk:
        wk = db.resolve_default_workflow_key(conn, request_type, dept=creator.dept) or request_type
    start_workflow(conn, request_id, creator=creator, request_type=request_type, workflow_key=wk)


def resolve_assignee(creator: AuthenticatedUser, step_row) -> tuple[int | None, str | None]:
    kind = str(step_row["assignee_kind"])
    value = None if step_row["assignee_value"] is None else str(step_row["assignee_value"])
    if kind == "manager":
        if creator.manager_id is not None:
            return (creator.manager_id, None)
        return (None, "admin")
    if kind == "role":
        return (None, value or "admin")
    if kind == "user":
        return (int(value), None) if value else (None, "admin")
    return (None, "admin")


def parse_int_list(value: str | None) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for part in str(value).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    seen = set()
    result: list[int] = []
    for i in out:
        if i in seen:
            continue
        seen.add(i)
        result.append(i)
    return result


def create_tasks_for_step(conn, request_id: int, *, creator: AuthenticatedUser, step_row) -> str:
    step_order = int(step_row["step_order"])
    step_key = str(step_row["step_key"])
    kind = str(step_row["assignee_kind"])
    value = None if step_row["assignee_value"] is None else str(step_row["assignee_value"])

    if kind in {"users_all", "users_any"}:
        v = (value or "").strip().lower()
        if v in {"all", "*", "everyone"}:
            rows = db.list_users(conn)
            user_ids = [int(r["id"]) for r in rows if int(r["id"]) != int(creator.id)]
        else:
            user_ids = parse_int_list(value)
        if not user_ids:
            db.create_task(
                conn,
                request_id,
                step_order=step_order,
                step_key=step_key,
                assignee_user_id=None,
                assignee_role="admin",
            )
            return step_key
        for uid in user_ids:
            db.create_task(
                conn,
                request_id,
                step_order=step_order,
                step_key=step_key,
                assignee_user_id=uid,
                assignee_role=None,
            )
        return step_key

    assignee_user_id, assignee_role = resolve_assignee(creator, step_row)
    db.create_task(
        conn,
        request_id,
        step_order=step_order,
        step_key=step_key,
        assignee_user_id=assignee_user_id,
        assignee_role=assignee_role,
    )
    return step_key


def start_workflow(conn, request_id: int, *, creator: AuthenticatedUser, request_type: str, workflow_key: str) -> None:
    steps = db.list_workflow_variant_steps(conn, workflow_key)
    if not steps and workflow_key != request_type:
        steps = db.list_workflow_variant_steps(conn, request_type)
    if not steps:
        steps = db.list_workflow_variant_steps(conn, "generic")
    if not steps:
        step_order = 1
        step_key = "admin"
        assignee_user_id, assignee_role = (None, "admin")
    else:
        req = db.get_request(conn, request_id)
        request_payload = workflow_conditions.parse_payload_json(req) if req else None
        step0 = (
            workflow_conditions.find_next_step(
                steps, current_order=None, request_payload=request_payload, creator_dept=creator.dept
            )
            or steps[0]
        )
        step_order = int(step0["step_order"])
        step_key = str(step0["step_key"])
        assignee_user_id, assignee_role = resolve_assignee(creator, step0)

    if steps:
        created_step_key = create_tasks_for_step(conn, request_id, creator=creator, step_row=step0)
        db.add_request_event(
            conn,
            request_id,
            event_type="task_created",
            actor_user_id=None,
            message=f"step={created_step_key}",
        )
    else:
        db.create_task(
            conn,
            request_id,
            step_order=step_order,
            step_key=step_key,
            assignee_user_id=assignee_user_id,
            assignee_role=assignee_role,
        )
        db.add_request_event(conn, request_id, event_type="task_created", actor_user_id=None, message=f"step={step_key}")

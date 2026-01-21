from __future__ import annotations

from .. import db
from ..auth import AuthenticatedUser
from . import workflow_conditions
from .workflow_engine import create_tasks_for_step


def can_act_on_task(user: AuthenticatedUser, task_row) -> bool:
    if task_row["assignee_user_id"] is not None and int(task_row["assignee_user_id"]) == user.id:
        return True
    if task_row["assignee_role"] is not None and str(task_row["assignee_role"]) == user.role:
        return True
    return False


def can_act_on_task_with_delegation(conn, user: AuthenticatedUser, task_row) -> bool:
    if can_act_on_task(user, task_row):
        return True
    if task_row["assignee_user_id"] is None:
        return False
    return db.is_active_delegate(conn, int(task_row["assignee_user_id"]), int(user.id))


def transfer_task(conn, user: AuthenticatedUser, task_id: int, *, assignee_user_id: int):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if user.role != "admin" and not can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    if not db.get_user_by_id(conn, int(assignee_user_id)):
        raise FileNotFoundError("user_not_found")

    db.transfer_task(conn, int(task_id), assignee_user_id=int(assignee_user_id))
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_transferred",
        actor_user_id=user.id,
        message=f"task={task_id} to_user_id={assignee_user_id}",
    )
    return db.get_request(conn, int(task["request_id"]))


def add_sign(conn, user: AuthenticatedUser, task_id: int, *, assignee_user_id: int):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    if not db.get_user_by_id(conn, int(assignee_user_id)):
        raise FileNotFoundError("user_not_found")

    db.create_task(
        conn,
        int(task["request_id"]),
        step_order=None if task["step_order"] is None else int(task["step_order"]),
        step_key=str(task["step_key"]),
        assignee_user_id=int(assignee_user_id),
        assignee_role=None,
    )
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_addsigned",
        actor_user_id=user.id,
        message=f"task={task_id} to_user_id={assignee_user_id}",
    )
    return db.get_request(conn, int(task["request_id"]))


def return_for_changes(conn, user: AuthenticatedUser, task_id: int, *, comment: str | None):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    request_id = int(task["request_id"])
    req = db.get_request(conn, request_id)
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    db.decide_task(conn, task_id, status="returned", decided_by=user.id, comment=comment)
    db.add_request_event(
        conn,
        request_id,
        event_type="task_returned",
        actor_user_id=user.id,
        message=f"task={task_id} step={task['step_key']}",
    )

    db.cancel_all_pending_tasks(conn, request_id, decided_by=user.id)
    db.mark_request_changes_requested(conn, request_id)
    db.add_request_event(
        conn,
        request_id,
        event_type="changes_requested",
        actor_user_id=user.id,
        message=comment,
    )
    db.create_resubmit_task(conn, request_id, int(req["user_id"]))
    db.add_request_event(conn, request_id, event_type="task_created", actor_user_id=None, message="step=resubmit")
    return db.get_request(conn, request_id)


def decide_task(conn, user: AuthenticatedUser, task_id: int, *, decision: str, comment: str | None):
    task = db.get_task(conn, task_id)
    if not task:
        raise FileNotFoundError("task_not_found")
    if str(task["status"]) != "pending":
        raise RuntimeError("task_already_decided")
    if not can_act_on_task_with_delegation(conn, user, task):
        raise PermissionError("not_authorized")

    req = db.get_request(conn, int(task["request_id"]))
    if not req:
        raise FileNotFoundError("request_not_found")
    if str(req["status"]) != "pending":
        raise RuntimeError("request_already_decided")

    db.decide_task(conn, task_id, status=decision, decided_by=user.id, comment=comment)
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="task_decided",
        actor_user_id=user.id,
        message=f"task={task_id} step={task['step_key']} decision={decision}",
    )

    request_type = str(req["request_type"])
    workflow_key = str(req["workflow_key"]) if "workflow_key" in req.keys() and req["workflow_key"] else None
    if not workflow_key:
        workflow_key = db.resolve_default_workflow_key(conn, request_type, dept=user.dept) or request_type
    steps = db.list_workflow_variant_steps(conn, workflow_key)
    if not steps and workflow_key != request_type:
        steps = db.list_workflow_variant_steps(conn, request_type)
    if not steps:
        steps = db.list_workflow_variant_steps(conn, "generic")

    current_order = task["step_order"]
    if current_order is None:
        current_order = None
        for s in steps:
            if str(s["step_key"]) == str(task["step_key"]):
                current_order = int(s["step_order"])
                break

    request_payload = workflow_conditions.parse_payload_json(req)
    creator_row = db.get_user_by_id(conn, int(req["user_id"]))
    creator_dept = None if creator_row["dept"] is None else str(creator_row["dept"])

    current_step_row = None
    if current_order is not None:
        for s in steps:
            if int(s["step_order"]) == int(current_order):
                current_step_row = s
                break
    current_assignee_kind = None if not current_step_row else str(current_step_row["assignee_kind"])
    is_users_any = current_assignee_kind == "users_any"
    is_users_all = current_assignee_kind == "users_all"

    if decision == "rejected":
        if is_users_any and current_order is not None:
            group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
            pending_left = any(str(t["status"]) == "pending" for t in group)
            approved_any = any(str(t["status"]) == "approved" for t in group)
            if pending_left or approved_any:
                return db.get_request(conn, int(task["request_id"]))

        db.update_request_status(conn, int(task["request_id"]), status="rejected", decided_by=user.id)
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="request_rejected",
            actor_user_id=user.id,
            message=comment,
        )
        return db.get_request(conn, int(task["request_id"]))

    if is_users_all and current_order is not None:
        group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
        if group and not all(str(t["status"]) == "approved" for t in group):
            return db.get_request(conn, int(task["request_id"]))

    if is_users_any and current_order is not None:
        db.cancel_pending_tasks_for_step(
            conn,
            int(task["request_id"]),
            int(current_order),
            except_task_id=int(task_id),
            decided_by=user.id,
        )

    if current_order is not None:
        group = db.list_tasks_for_step(conn, int(task["request_id"]), int(current_order))
        if any(str(t["status"]) == "pending" for t in group):
            return db.get_request(conn, int(task["request_id"]))

    next_step_row = workflow_conditions.find_next_step(
        steps, current_order=current_order, request_payload=request_payload, creator_dept=creator_dept
    )

    if next_step_row is not None:
        creator = AuthenticatedUser(
            id=int(creator_row["id"]),
            username=str(creator_row["username"]),
            role=str(creator_row["role"]),
            dept=None if creator_row["dept"] is None else str(creator_row["dept"]),
            manager_id=None if creator_row["manager_id"] is None else int(creator_row["manager_id"]),
        )
        create_tasks_for_step(conn, int(task["request_id"]), creator=creator, step_row=next_step_row)
        db.add_request_event(
            conn,
            int(task["request_id"]),
            event_type="task_created",
            actor_user_id=None,
            message=f"step={next_step_row['step_key']}",
        )
        db.update_request_status(conn, int(task["request_id"]), status="pending", decided_by=None)
        return db.get_request(conn, int(task["request_id"]))

    db.update_request_status(conn, int(task["request_id"]), status="approved", decided_by=user.id)
    db.add_request_event(
        conn,
        int(task["request_id"]),
        event_type="request_approved",
        actor_user_id=user.id,
        message=comment,
    )
    return db.get_request(conn, int(task["request_id"]))


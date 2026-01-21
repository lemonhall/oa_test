from __future__ import annotations

import json
from typing import Any


def row_to_request(row) -> dict[str, Any]:
    payload_obj = None
    if "payload_json" in row.keys() and row["payload_json"] is not None:
        try:
            payload_obj = json.loads(str(row["payload_json"]))
        except Exception:
            payload_obj = None
    keys = set(row.keys())
    return {
        "id": int(row["id"]),
        "type": str(row["request_type"]) if "request_type" in row.keys() else "generic",
        "workflow": (
            None
            if "workflow_key" not in keys or row["workflow_key"] is None
            else {
                "key": str(row["workflow_key"]),
                "name": None if "workflow_name" not in keys or row["workflow_name"] is None else str(row["workflow_name"]),
                "category": None
                if "workflow_category" not in keys or row["workflow_category"] is None
                else str(row["workflow_category"]),
                "scope_kind": None
                if "workflow_scope_kind" not in keys or row["workflow_scope_kind"] is None
                else str(row["workflow_scope_kind"]),
                "scope_value": None
                if "workflow_scope_value" not in keys or row["workflow_scope_value"] is None
                else str(row["workflow_scope_value"]),
            }
        ),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "payload": payload_obj,
        "status": str(row["status"]),
        "created_at": int(row["created_at"]),
        "updated_at": None if row["updated_at"] is None else int(row["updated_at"]),
        "owner": {"id": int(row["user_id"]), "username": str(row["owner_username"])},
        "pending_task": (
            None
            if row["pending_task_id"] is None
            else {
                "id": int(row["pending_task_id"]),
                "step_key": str(row["pending_step_key"]),
                "assignee_user_id": None if row["pending_assignee_user_id"] is None else int(row["pending_assignee_user_id"]),
                "assignee_username": None
                if row["pending_assignee_username"] is None
                else str(row["pending_assignee_username"]),
                "assignee_role": None if row["pending_assignee_role"] is None else str(row["pending_assignee_role"]),
            }
        ),
        "decided_by": (
            None
            if row["decided_by"] is None
            else {"id": int(row["decided_by"]), "username": str(row["decided_by_username"])}
        ),
        "decided_at": None if row["decided_at"] is None else int(row["decided_at"]),
    }


def row_to_task(row) -> dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "step_key": str(row["step_key"]),
        "assignee_user_id": None if row["assignee_user_id"] is None else int(row["assignee_user_id"]),
        "assignee_role": None if row["assignee_role"] is None else str(row["assignee_role"]),
        "assignee_username": None
        if "assignee_username" not in keys or row["assignee_username"] is None
        else str(row["assignee_username"]),
        "status": str(row["status"]),
        "decided_by": None if row["decided_by"] is None else int(row["decided_by"]),
        "decided_by_username": None
        if "decided_by_username" not in keys or row["decided_by_username"] is None
        else str(row["decided_by_username"]),
        "decided_at": None if row["decided_at"] is None else int(row["decided_at"]),
        "comment": None if row["comment"] is None else str(row["comment"]),
        "created_at": int(row["created_at"]),
    }


def row_to_event(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "event_type": str(row["event_type"]),
        "actor_user_id": None if row["actor_user_id"] is None else int(row["actor_user_id"]),
        "actor_username": None if row["actor_username"] is None else str(row["actor_username"]),
        "message": None if row["message"] is None else str(row["message"]),
        "created_at": int(row["created_at"]),
    }


def row_to_notification(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": None if row["request_id"] is None else int(row["request_id"]),
        "event_type": str(row["event_type"]),
        "actor_user_id": None if row["actor_user_id"] is None else int(row["actor_user_id"]),
        "actor_username": None if row["actor_username"] is None else str(row["actor_username"]),
        "message": None if row["message"] is None else str(row["message"]),
        "created_at": int(row["created_at"]),
        "read_at": None if row["read_at"] is None else int(row["read_at"]),
    }


def row_to_attachment(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "request_id": int(row["request_id"]),
        "filename": str(row["filename"]),
        "content_type": None if row["content_type"] is None else str(row["content_type"]),
        "size": int(row["size"]),
        "uploader_user_id": int(row["uploader_user_id"]),
        "uploader_username": None
        if "uploader_username" not in row.keys() or row["uploader_username"] is None
        else str(row["uploader_username"]),
        "created_at": int(row["created_at"]),
    }


def row_to_inbox_task(row) -> dict[str, Any]:
    return {
        "task": row_to_task(row),
        "request": {
            "id": int(row["request_id"]),
            "type": str(row["request_type"]),
            "title": str(row["title"]),
            "body": str(row["body"]),
            "status": str(row["request_status"]),
            "created_at": int(row["request_created_at"]),
            "owner_username": str(row["owner_username"]),
        },
    }


def row_to_user(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "role": str(row["role"]),
        "dept": None if row["dept"] is None else str(row["dept"]),
        "dept_id": None if row["dept_id"] is None else int(row["dept_id"]),
        "position": None if row["position"] is None else str(row["position"]),
        "manager_id": None if row["manager_id"] is None else int(row["manager_id"]),
        "manager_username": None if row["manager_username"] is None else str(row["manager_username"]),
        "created_at": int(row["created_at"]),
    }


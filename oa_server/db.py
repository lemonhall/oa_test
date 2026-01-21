from __future__ import annotations

"""Public DB API.

This module is intentionally thin; implementation lives in `oa_server._db`.
"""

from ._db.attachments import create_attachment, get_attachment, list_request_attachments
from ._db.connection import _connect_raw, connect
from ._db.delegations import get_delegation, is_active_delegate, set_delegation
from ._db.events import add_request_event, add_request_watcher, list_request_events, list_request_watchers
from ._db.notifications import list_notifications, mark_notification_read
from ._db.org import create_department, get_department, list_departments
from ._db.rbac import (
    ensure_default_roles,
    list_role_permissions,
    list_roles,
    replace_role_permissions,
    role_exists,
    role_has_permission,
    upsert_role,
)
from ._db.requests import (
    create_request,
    decide_request,
    get_request,
    list_requests,
    mark_request_changes_requested,
    reset_request_for_resubmit,
    update_request_status,
)
from ._db.schema import init_db
from ._db.tasks import (
    cancel_all_pending_tasks,
    cancel_pending_tasks_for_step,
    create_resubmit_task,
    create_task,
    decide_task,
    get_task,
    list_inbox_tasks,
    list_request_tasks,
    list_tasks_for_step,
    transfer_task,
)
from ._db.users import (
    create_session,
    delete_session,
    get_session_with_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user,
)
from ._db.workflow_variants import (
    delete_workflow_variant,
    ensure_workflow_variants,
    get_workflow_variant,
    list_available_workflow_variants,
    list_workflow_steps,
    list_workflow_variant_steps,
    list_workflow_variants_admin,
    list_workflows,
    migrate_workflow_variants,
    replace_workflow_steps,
    replace_workflow_variant_steps,
    resolve_default_workflow_key,
    upsert_workflow_variant,
)
from ._db.workflows_legacy import ensure_default_workflows, migrate_workflows

__all__ = [
    "_connect_raw",
    "connect",
    "init_db",
    # users / sessions
    "get_user_by_username",
    "get_user_by_id",
    "list_users",
    "update_user",
    "create_session",
    "delete_session",
    "get_session_with_user",
    # requests
    "create_request",
    "list_requests",
    "get_request",
    "update_request_status",
    "mark_request_changes_requested",
    "reset_request_for_resubmit",
    "decide_request",
    # tasks
    "create_task",
    "list_inbox_tasks",
    "get_task",
    "decide_task",
    "transfer_task",
    "list_request_tasks",
    "list_tasks_for_step",
    "cancel_pending_tasks_for_step",
    "create_resubmit_task",
    "cancel_all_pending_tasks",
    # workflows (legacy + v2)
    "ensure_default_workflows",
    "migrate_workflows",
    "ensure_workflow_variants",
    "migrate_workflow_variants",
    "list_workflows",
    "list_workflow_steps",
    "replace_workflow_steps",
    "get_workflow_variant",
    "list_available_workflow_variants",
    "upsert_workflow_variant",
    "replace_workflow_variant_steps",
    "delete_workflow_variant",
    "list_workflow_variants_admin",
    "resolve_default_workflow_key",
    "list_workflow_variant_steps",
    # events / watchers
    "add_request_event",
    "add_request_watcher",
    "list_request_watchers",
    "list_request_events",
    # notifications
    "list_notifications",
    "mark_notification_read",
    # attachments
    "create_attachment",
    "get_attachment",
    "list_request_attachments",
    # roles / rbac
    "ensure_default_roles",
    "upsert_role",
    "replace_role_permissions",
    "list_roles",
    "list_role_permissions",
    "role_exists",
    "role_has_permission",
    # delegation
    "set_delegation",
    "get_delegation",
    "is_active_delegate",
    # org
    "create_department",
    "get_department",
    "list_departments",
]

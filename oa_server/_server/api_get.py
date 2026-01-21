from __future__ import annotations

from . import api_get_admin, api_get_attachments, api_get_inbox, api_get_me, api_get_notifications, api_get_requests, api_get_users, api_get_workflows


def handle(handler, path: str, query: str) -> bool:
    for mod in (
        api_get_me,
        api_get_workflows,
        api_get_admin,
        api_get_requests,
        api_get_inbox,
        api_get_notifications,
        api_get_attachments,
        api_get_users,
    ):
        if mod.try_handle(handler, path, query):
            return True
    return False


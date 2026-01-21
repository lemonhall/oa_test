from __future__ import annotations

from . import api_post_admin, api_post_auth, api_post_delegation, api_post_notifications, api_post_requests, api_post_tasks, api_post_users


def handle(handler, path: str, query: str) -> bool:
    for mod in (
        api_post_auth,
        api_post_delegation,
        api_post_requests,
        api_post_tasks,
        api_post_notifications,
        api_post_users,
        api_post_admin,
    ):
        if mod.try_handle(handler, path, query):
            return True
    return False


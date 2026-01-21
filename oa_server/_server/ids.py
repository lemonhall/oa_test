from __future__ import annotations


def parse_request_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def parse_task_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def parse_notification_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def parse_attachment_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


def parse_user_id(path: str, suffix: str) -> int:
    core = path if not suffix else path[: -len(suffix)]
    parts = core.split("/")
    return int(parts[-1])


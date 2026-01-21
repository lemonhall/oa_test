from __future__ import annotations

from typing import Any

from . import assets, compliance, finance, hr_people, hr_time, it, legal, logistics, procurement
from ..jsonutil import json_dumps


def build_request_from_payload(
    request_type: str,
    *,
    title: str,
    body: str,
    payload: dict[str, Any] | None,
) -> tuple[str, str, str | None]:
    if payload is None:
        return title, body, None

    for mod in (hr_time, hr_people, finance, procurement, assets, legal, it, logistics, compliance):
        handled, title, body, payload_json = mod.try_build(request_type, title=title, body=body, payload=payload)
        if handled:
            return title, body, payload_json

    return title, body, json_dumps(payload)


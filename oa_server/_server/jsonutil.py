from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def read_json(handler: BaseHTTPRequestHandler) -> Any:
    length_s = handler.headers.get("Content-Length", "0")
    try:
        length = int(length_s)
    except ValueError:
        length = 0
    raw = handler.rfile.read(length) if length > 0 else b""
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


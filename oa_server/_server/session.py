from __future__ import annotations

import os


SESSION_COOKIE = "oa_session"
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


def build_session_cookie(token: str, *, expires_immediately: bool = False) -> str:
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax"]
    if os.environ.get("OA_COOKIE_SECURE") == "1":
        parts.append("Secure")
    if expires_immediately:
        parts.append("Max-Age=0")
    return "; ".join(parts)


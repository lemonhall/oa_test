from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass


PBKDF2_ALG = "sha256"
PBKDF2_ITERATIONS = 210_000
SALT_BYTES = 16
DKLEN = 32


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(PBKDF2_ALG, password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=DKLEN)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(dk).decode("ascii").rstrip("="),
    )


def _b64decode_nopad(value: str) -> bytes:
    pad = "=" * ((4 - (len(value) % 4)) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters_s, salt_s, hash_s = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64decode_nopad(salt_s)
        expected = _b64decode_nopad(hash_s)
    except Exception:
        return False

    dk = hashlib.pbkdf2_hmac(PBKDF2_ALG, password.encode("utf-8"), salt, iters, dklen=len(expected))
    return hmac.compare_digest(dk, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def parse_cookie_header(cookie_header: str | None) -> dict[str, str]:
    if not cookie_header:
        return {}
    result: dict[str, str] = {}
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str


"""Verified internal service-to-service identity assertion between NestJS and FastAPI.

FastAPI /chat endpoints are private to the JWT-guarded NestJS backend.
Direct public calls or spoofed body/query user_id values are rejected fail-closed.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.config import settings

INTERNAL_ASSERTION_HEADER = "X-WanderAI-Internal-Assertion"
EXPECTED_ISSUER = "wanderai-backend"
EXPECTED_AUDIENCE = "wanderai-ai-service"
MIN_INTERNAL_SECRET_LENGTH = 32
MIN_INTERNAL_SECRET_UNIQUE_CHARS = 8
MAX_ASSERTION_TTL_SECONDS = 120
CLOCK_SKEW_TOLERANCE_SECONDS = 15

_DISALLOWED_SECRETS = {
    "super-secret",
    "wanderai-dev-jwt-secret-2026",
    "wanderai-dev-refresh-secret-2026",
    "wanderai-jwt-secret-change-in-production",
    "wanderai-refresh-secret-change-in-production",
    "<replace_with_distinct_internal_service_secret_min_32_chars>",
    "dummy-key-not-used-in-ci",
    "dummy-key-for-openapi-export",
    "changeme",
    "secret",
    "password",
}


class InternalAuthConfigError(Exception):
    """Raised when AI_INTERNAL_AUTH_SECRET is missing or weak on the server."""


class InternalAuthError(Exception):
    """Raised when an incoming internal service assertion is missing, invalid, or forbidden."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class InternalPrincipal:
    """Verified user identity asserted by the NestJS AI proxy."""

    user_id: str
    bound_session_id: Optional[str] = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * ((4 - (len(encoded) % 4)) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def validate_internal_secret(raw_secret: Optional[str]) -> str:
    """Validate that AI_INTERNAL_AUTH_SECRET is configured and strong."""
    if not isinstance(raw_secret, str) or not raw_secret.strip():
        raise InternalAuthConfigError(
            "Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET is required."
        )

    secret = raw_secret.strip()
    normalized = secret.lower()
    if (
        normalized in _DISALLOWED_SECRETS
        or normalized.startswith("<replace_with_")
        or "change-in-production" in normalized
        or "wanderai-dev-" in normalized
    ):
        raise InternalAuthConfigError(
            "Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET uses a disallowed placeholder."
        )

    if len(secret) < MIN_INTERNAL_SECRET_LENGTH:
        raise InternalAuthConfigError(
            f"Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET must be at least {MIN_INTERNAL_SECRET_LENGTH} characters."
        )

    if len(set(secret)) < MIN_INTERNAL_SECRET_UNIQUE_CHARS:
        raise InternalAuthConfigError(
            "Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET lacks character diversity."
        )

    jwt_secret = (os.environ.get("JWT_SECRET") or "").strip()
    jwt_refresh_secret = (os.environ.get("JWT_REFRESH_SECRET") or "").strip()
    if (jwt_secret and secret == jwt_secret) or (
        jwt_refresh_secret and secret == jwt_refresh_secret
    ):
        raise InternalAuthConfigError(
            "Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET must be distinct from JWT secrets."
        )

    return secret


def create_internal_assertion(
    secret: str,
    user_id: str,
    action: str,
    session_id: Optional[str] = None,
    now: Optional[int] = None,
    ttl_seconds: int = 60,
) -> str:
    """Create a short-lived HMAC-SHA256 assertion bound to user_id, action, and optional session_id."""
    validated_secret = validate_internal_secret(secret)
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")

    issued_at = int(time.time()) if now is None else int(now)
    payload = {
        "iss": EXPECTED_ISSUER,
        "aud": EXPECTED_AUDIENCE,
        "sub": user_id.strip(),
        "act": action.strip(),
        "sid": session_id.strip() if isinstance(session_id, str) and session_id.strip() else "",
        "iat": issued_at,
        "exp": issued_at + int(ttl_seconds),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    signing_input = f"v1.{payload_b64}".encode("ascii")
    sig_bytes = hmac.new(validated_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig_bytes)
    return f"v1.{payload_b64}.{sig_b64}"


def verify_internal_assertion(
    token: Optional[str],
    secret: Optional[str],
    expected_action: str,
    now: Optional[int] = None,
) -> InternalPrincipal:
    """Verify HMAC-SHA256 signature, issuer, audience, expiry, and request action binding."""
    validated_secret = validate_internal_secret(secret)

    if not isinstance(token, str) or not token.strip():
        raise InternalAuthError(
            status_code=401,
            detail="Missing internal service authentication assertion.",
        )

    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != "v1" or not parts[1] or not parts[2]:
        raise InternalAuthError(
            status_code=401,
            detail="Malformed internal service authentication assertion.",
        )

    _, payload_b64, sig_b64 = parts
    signing_input = f"v1.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        validated_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()

    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise InternalAuthError(
            status_code=401,
            detail="Malformed internal service assertion signature.",
        ) from exc

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise InternalAuthError(
            status_code=401,
            detail="Invalid internal service assertion signature.",
        )

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise InternalAuthError(
            status_code=401,
            detail="Malformed internal service assertion payload.",
        ) from exc

    if not isinstance(payload, dict):
        raise InternalAuthError(
            status_code=401,
            detail="Invalid internal service assertion payload.",
        )

    if payload.get("iss") != EXPECTED_ISSUER or payload.get("aud") != EXPECTED_AUDIENCE:
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion issuer or audience mismatch.",
        )

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion is missing authenticated subject.",
        )

    act = payload.get("act")
    if act != expected_action:
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion action binding mismatch.",
        )

    iat = payload.get("iat")
    exp = payload.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int) or exp < iat:
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion has invalid timestamps.",
        )

    if (exp - iat) > MAX_ASSERTION_TTL_SECONDS:
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion TTL exceeds maximum allowed window.",
        )

    current_time = int(time.time()) if now is None else int(now)
    if iat > current_time + CLOCK_SKEW_TOLERANCE_SECONDS:
        raise InternalAuthError(
            status_code=403,
            detail="Internal service assertion issued in the future.",
        )
    if current_time > exp + CLOCK_SKEW_TOLERANCE_SECONDS:
        raise InternalAuthError(
            status_code=401,
            detail="Internal service assertion has expired.",
        )

    raw_sid = payload.get("sid")
    bound_sid = raw_sid.strip() if isinstance(raw_sid, str) and raw_sid.strip() else None
    return InternalPrincipal(user_id=sub.strip(), bound_session_id=bound_sid)


async def require_internal_principal(
    request: Request,
    x_wanderai_internal_assertion: Optional[str] = Header(
        default=None,
        alias=INTERNAL_ASSERTION_HEADER,
        include_in_schema=False,
    ),
) -> InternalPrincipal:
    """FastAPI dependency enforcing verified internal identity assertion on /chat endpoints."""
    expected_action = f"{request.method.upper()}:{request.url.path}"
    try:
        return verify_internal_assertion(
            token=x_wanderai_internal_assertion,
            secret=settings.AI_INTERNAL_AUTH_SECRET,
            expected_action=expected_action,
        )
    except InternalAuthConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail="Dịch vụ AI chưa được cấu hình khóa xác thực nội bộ.",
        ) from exc
    except InternalAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc

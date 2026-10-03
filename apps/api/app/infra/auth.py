"""Verification of the access token issued by supabase-auth (API_SPEC 2, SECURITY_NOTES SEC-05/06).

Pure function of the token and the settings: no network call, no Supabase or Redis client. The
signing secret is read here and nowhere else (an architecture test keeps it that way).
"""

import uuid
from dataclasses import dataclass
from typing import Final

import jwt

from app.api.errors import AppError, ErrorCode
from app.config import ConfigError, Settings, get_settings
from app.infra.observability import get_logger

ALGORITHMS: Final = ["HS256"]  # never read from the token header: "none" and others are refused
AUDIENCE: Final = "authenticated"
REQUIRED_CLAIMS: Final = ["exp", "sub", "aud", "iss"]
# gotrue and the api run on different clocks: a fresh token must not be refused as "not yet valid".
LEEWAY_SECONDS: Final = 10
UNAUTHENTICATED_MESSAGE: Final = "Authentication is required. Please sign in."
EXPIRED_MESSAGE: Final = "Your session has expired. Please sign in again."
CHALLENGE_HEADERS: Final = {"WWW-Authenticate": "Bearer"}

logger = get_logger("app.auth")


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    expires_at: int  # epoch seconds (`exp`)


def unauthenticated() -> AppError:
    return AppError(
        ErrorCode.UNAUTHENTICATED, 401, UNAUTHENTICATED_MESSAGE, headers=CHALLENGE_HEADERS
    )


def _refuse(reason: str) -> AppError:
    """Log the closed-list reason (never the token) and build the 401."""
    logger.warning("auth_failed", reason=reason)
    if reason == "expired":
        return AppError(ErrorCode.TOKEN_EXPIRED, 401, EXPIRED_MESSAGE, headers=CHALLENGE_HEADERS)
    return unauthenticated()


def _failure_reason(error: Exception) -> str:
    if isinstance(error, jwt.ExpiredSignatureError):
        return "expired"
    if isinstance(error, jwt.InvalidSignatureError | jwt.InvalidAlgorithmError):
        return "bad_signature"
    if isinstance(error, jwt.DecodeError | ValueError):
        return "malformed"
    return "bad_claims"


def verify_access_token(token: str, settings: Settings | None = None) -> TokenClaims:
    """Return the user and the expiry of a valid access token, or raise a 401 `AppError`.

    An empty secret or issuer is a deployment mistake: `ConfigError` (a loud 500), never a 401.
    """
    settings = settings or get_settings()
    secret = settings.supabase_jwt_secret.get_secret_value()
    issuer = settings.supabase_jwt_issuer
    if not secret:
        raise ConfigError("SUPABASE_JWT_SECRET is empty. Run 'make env-local' to generate it.")
    if not issuer:
        raise ConfigError("SUPABASE_JWT_ISSUER is empty. Set it to <public URL>/auth/v1.")
    if not token or not token.strip():
        raise _refuse("missing")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=issuer,
            options={"require": REQUIRED_CLAIMS},
            leeway=LEEWAY_SECONDS,
        )
    except (jwt.PyJWTError, ValueError) as error:
        raise _refuse(_failure_reason(error)) from None
    # The anon and service keys share the signing secret: only a signed-in user may pass.
    if claims.get("role") != AUDIENCE:
        raise _refuse("bad_claims")
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        raise _refuse("bad_claims") from None
    return TokenClaims(user_id=user_id, expires_at=int(claims["exp"]))

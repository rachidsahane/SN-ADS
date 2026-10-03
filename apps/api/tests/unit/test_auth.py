"""infra/auth.py: verification of the access token issued by supabase-auth (API_SPEC 2, SEC-05/06).

Tokens are signed at run time with a throw-away secret. The forged ones cover SECURITY_NOTES SEC-05:
other key, other algorithm, other environment (audience/issuer), anon and service keys as bearer.
"""

import base64
import json
import time
import uuid
from collections.abc import Callable

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from app.api.errors import AppError, ErrorCode
from app.config import ConfigError, Settings
from app.infra.auth import TokenClaims, verify_access_token
from app.infra.observability import configure_logging
from tests.support import JWT_ISSUER, JWT_SECRET, OTHER_JWT_SECRET

MakeToken = Callable[..., str]

UNAUTHENTICATED_MESSAGE = "Authentication is required. Please sign in."
EXPIRED_MESSAGE = "Your session has expired. Please sign in again."


def _refusal(token: str, settings: Settings) -> AppError:
    with pytest.raises(AppError) as error:
        verify_access_token(token, settings)
    return error.value


def _assert_unauthenticated(token: str, settings: Settings) -> None:
    refusal = _refusal(token, settings)
    assert refusal.code is ErrorCode.UNAUTHENTICATED
    assert refusal.status == 401
    assert refusal.message == UNAUTHENTICATED_MESSAGE
    assert refusal.headers == {"WWW-Authenticate": "Bearer"}


def test_a_valid_token_returns_the_user_and_the_expiry(
    settings: Settings, make_access_token: MakeToken
) -> None:
    user_id = uuid.uuid4()
    before = int(time.time())
    claims = verify_access_token(make_access_token(sub=user_id, expires_in=600), settings)
    assert isinstance(claims, TokenClaims)
    assert claims.user_id == user_id
    assert isinstance(claims.user_id, uuid.UUID)
    assert before + 600 <= claims.expires_at <= before + 605


def test_claims_are_immutable(settings: Settings, make_access_token: MakeToken) -> None:
    claims = verify_access_token(make_access_token(), settings)
    with pytest.raises(AttributeError):
        claims.user_id = uuid.uuid4()  # type: ignore[misc]


def test_the_settings_argument_is_optional_and_defaults_to_the_application_settings(
    monkeypatch: pytest.MonkeyPatch, make_access_token: MakeToken
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", JWT_ISSUER)
    get_settings.cache_clear()
    try:
        assert verify_access_token(make_access_token()).user_id
    finally:
        get_settings.cache_clear()


# --- expiry ------------------------------------------------------------------------------------


def test_an_expired_token_is_token_expired(
    settings: Settings, make_access_token: MakeToken
) -> None:
    refusal = _refusal(make_access_token(expires_in=-3600), settings)
    assert refusal.code is ErrorCode.TOKEN_EXPIRED
    assert refusal.status == 401
    assert refusal.message == EXPIRED_MESSAGE
    assert refusal.headers == {"WWW-Authenticate": "Bearer"}


def test_a_token_expired_by_more_than_the_leeway_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    assert _refusal(make_access_token(expires_in=-30), settings).code is ErrorCode.TOKEN_EXPIRED


def test_a_token_expired_by_less_than_the_ten_second_leeway_is_accepted(
    settings: Settings, make_access_token: MakeToken
) -> None:
    assert verify_access_token(make_access_token(expires_in=-3), settings).user_id


def test_a_token_issued_a_few_seconds_in_the_future_is_accepted(
    settings: Settings, make_access_token: MakeToken
) -> None:
    """Clock skew between gotrue and the api must not refuse a fresh token as 'not yet valid'."""
    assert verify_access_token(make_access_token(issued_in=5), settings).user_id


def test_an_expired_token_with_a_wrong_signature_is_not_reported_as_expired(
    settings: Settings, make_access_token: MakeToken
) -> None:
    """Only a token we signed may learn that it merely expired."""
    forged = make_access_token(expires_in=-3600, key=OTHER_JWT_SECRET)
    assert _refusal(forged, settings).code is ErrorCode.UNAUTHENTICATED


# --- forged tokens (SEC-05) --------------------------------------------------------------------


def test_a_token_signed_with_another_secret_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    _assert_unauthenticated(make_access_token(key=OTHER_JWT_SECRET), settings)


def test_a_token_whose_payload_was_edited_after_signing_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    header, payload, signature = make_access_token().split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = str(uuid.uuid4())  # someone else's id, same signature
    edited = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    _assert_unauthenticated(f"{header}.{edited}.{signature}", settings)


def test_alg_none_is_refused(settings: Settings, make_access_token: MakeToken) -> None:
    _assert_unauthenticated(make_access_token(key=None, algorithm="none"), settings)


@pytest.mark.parametrize("algorithm", ["HS384", "HS512"])
def test_other_hmac_algorithms_are_refused_even_with_the_right_secret(
    settings: Settings, make_access_token: MakeToken, algorithm: str
) -> None:
    _assert_unauthenticated(make_access_token(algorithm=algorithm), settings)


def test_an_asymmetric_token_is_refused(settings: Settings, make_access_token: MakeToken) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": JWT_ISSUER,
            "role": "authenticated",
            "exp": int(time.time()) + 600,
        },
        private_key,
        algorithm="RS256",
    )
    _assert_unauthenticated(token, settings)


def test_a_token_from_another_audience_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    _assert_unauthenticated(make_access_token(aud="service"), settings)


def test_a_token_from_another_environment_issuer_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    _assert_unauthenticated(make_access_token(iss="https://staging.example.test/auth/v1"), settings)


@pytest.mark.parametrize("missing", ["sub", "exp", "aud", "iss"])
def test_a_token_without_a_required_claim_is_refused(
    settings: Settings, make_access_token: MakeToken, missing: str
) -> None:
    if missing == "exp":
        token = make_access_token(expires_in=None)
    else:
        token = make_access_token(drop=(missing,))
    _assert_unauthenticated(token, settings)


@pytest.mark.parametrize("sub", ["not-a-uuid", "12345", "' OR 1=1 --", "../../etc/passwd"])
def test_a_subject_that_is_not_a_uuid_is_refused(
    settings: Settings, make_access_token: MakeToken, sub: str
) -> None:
    _assert_unauthenticated(make_access_token(sub=sub), settings)


@pytest.mark.parametrize("role", ["anon", "service_role", "admin", "supabase_admin", ""])
def test_a_token_whose_role_is_not_authenticated_is_refused(
    settings: Settings, make_access_token: MakeToken, role: str
) -> None:
    """The anon and service keys are signed with the same secret: they must not pass as users."""
    _assert_unauthenticated(make_access_token(role=role), settings)


def test_a_token_without_a_role_is_refused(
    settings: Settings, make_access_token: MakeToken
) -> None:
    _assert_unauthenticated(make_access_token(drop=("role",)), settings)


def test_the_anon_and_service_keys_are_refused_as_bearer(
    settings: Settings, make_access_token: MakeToken
) -> None:
    """Shape of the real keys: role anon / service_role, no `sub`, long expiry, same secret."""
    for role in ("anon", "service_role"):
        key = make_access_token(role=role, drop=("sub", "session_id"), expires_in=10 * 365 * 86400)
        _assert_unauthenticated(key, settings)


@pytest.mark.parametrize(
    "garbage",
    ["", " ", "abc", "a.b", "a.b.c", "....", "Bearer abc", "x" * 5000, "\x00\x01", "é.è.à"],
)
def test_garbage_is_unauthenticated_and_never_raises_anything_else(
    settings: Settings, garbage: str
) -> None:
    _assert_unauthenticated(garbage, settings)


def test_every_refusal_carries_the_www_authenticate_header(
    settings: Settings, make_access_token: MakeToken
) -> None:
    tokens = [
        make_access_token(expires_in=-3600),
        make_access_token(key=OTHER_JWT_SECRET),
        make_access_token(aud="other"),
        "garbage",
    ]
    for token in tokens:
        assert _refusal(token, settings).headers == {"WWW-Authenticate": "Bearer"}


# --- configuration ----------------------------------------------------------------------------


def test_an_empty_secret_is_a_loud_configuration_error_never_a_401(
    settings: Settings, make_access_token: MakeToken
) -> None:
    broken = settings.model_copy(update={"supabase_jwt_secret": SecretStr("")})
    with pytest.raises(ConfigError, match="SUPABASE_JWT_SECRET"):
        verify_access_token(make_access_token(), broken)


def test_an_empty_issuer_is_a_loud_configuration_error_never_a_401(
    settings: Settings, make_access_token: MakeToken
) -> None:
    broken = settings.model_copy(update={"supabase_jwt_issuer": ""})
    with pytest.raises(ConfigError, match="SUPABASE_JWT_ISSUER"):
        verify_access_token(make_access_token(), broken)


def test_a_configuration_error_does_not_echo_the_secret(
    settings: Settings, make_access_token: MakeToken
) -> None:
    broken = settings.model_copy(update={"supabase_jwt_issuer": ""})
    with pytest.raises(ConfigError) as error:
        verify_access_token(make_access_token(), broken)
    assert JWT_SECRET not in str(error.value)


# --- logs -------------------------------------------------------------------------------------


def _entries(out: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


@pytest.mark.parametrize(
    ("build", "reason"),
    [
        (lambda make: make(expires_in=-3600), "expired"),
        (lambda make: make(key=OTHER_JWT_SECRET), "bad_signature"),
        (lambda make: make(aud="other"), "bad_claims"),
        (lambda make: "not.a.token", "malformed"),
    ],
)
def test_a_refusal_is_logged_as_a_warning_with_a_reason_and_nothing_else_sensitive(
    settings: Settings,
    make_access_token: MakeToken,
    capsys: pytest.CaptureFixture[str],
    build: Callable[[MakeToken], str],
    reason: str,
) -> None:
    configure_logging(settings)
    token = build(make_access_token)
    with pytest.raises(Exception):  # noqa: B017  # the refusal type is checked elsewhere
        verify_access_token(token, settings)
    out = capsys.readouterr().out
    entry = next(e for e in _entries(out) if e["event"] == "auth_failed")
    assert (entry["level"], entry["reason"]) == ("warning", reason)
    assert token not in out
    assert JWT_SECRET not in out
    assert OTHER_JWT_SECRET not in out
    assert "someone@example.test" not in out


@pytest.mark.parametrize("token", ["", "x" * 40])
def test_failure_reasons_stay_in_the_closed_list(
    settings: Settings, capsys: pytest.CaptureFixture[str], token: str
) -> None:
    configure_logging(settings)
    with pytest.raises(Exception):  # noqa: B017
        verify_access_token(token, settings)
    entry = next(e for e in _entries(capsys.readouterr().out) if e["event"] == "auth_failed")
    assert entry["reason"] in {"missing", "malformed", "expired", "bad_signature", "bad_claims"}


def test_a_valid_token_logs_nothing_at_warning_level(
    settings: Settings, make_access_token: MakeToken, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)
    verify_access_token(make_access_token(), settings)
    assert "auth_failed" not in capsys.readouterr().out

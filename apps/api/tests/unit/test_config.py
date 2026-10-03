import pytest

from app.config import ConfigError, Settings, load_e2e_accounts, load_settings

E2E_ACCOUNTS = ("ADMIN", "ADMIN2", "MARKETER_A", "MARKETER_B", "RESET")
E2E_VARIABLES = (
    *(f"E2E_{name}_{kind}" for name in E2E_ACCOUNTS for kind in ("EMAIL", "PASSWORD")),
    "E2E_INVITEE_EMAIL",
)

ALL_VARIABLES = (
    "APP_ENV", "SERVICE_NAME", "APP_RELEASE", "LOG_LEVEL",
    "SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "MAX_UPLOAD_BYTES",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET", "SUPABASE_JWT_ISSUER", "REDIS_URL", "WEB_APP_URL",
    "FIRST_ADMIN_EMAIL", "FIRST_ADMIN_FULL_NAME", *E2E_VARIABLES,
)  # fmt: skip


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ALL_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SERVICE_NAME", "worker")
    monkeypatch.setenv("APP_RELEASE", "abc1234")
    settings = load_settings()
    assert (settings.app_env, settings.service_name, settings.app_release) == (
        "staging", "worker", "abc1234",
    )  # fmt: skip


def test_optional_variables_have_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    settings = load_settings()
    assert settings.app_release == "local"
    assert settings.log_level == "INFO"
    assert settings.sentry_dsn == ""
    assert settings.sentry_traces_sample_rate == 0.0
    assert settings.max_upload_bytes == 10_485_760
    assert not settings.is_production


def test_missing_variables_are_all_listed_in_one_message() -> None:
    with pytest.raises(ConfigError) as error:
        load_settings()
    assert "APP_ENV" in str(error.value)
    assert "SERVICE_NAME" in str(error.value)


def test_invalid_value_names_the_variable_without_echoing_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("LOG_LEVEL", "super-secret-value")
    with pytest.raises(ConfigError) as error:
        load_settings()
    assert "LOG_LEVEL" in str(error.value)
    assert "super-secret-value" not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


def test_sample_rate_must_be_a_fraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "1.5")
    with pytest.raises(ConfigError, match="SENTRY_TRACES_SAMPLE_RATE"):
        load_settings()


def test_production_flag(settings: Settings) -> None:
    assert settings.model_copy(update={"app_env": "production"}).is_production


def test_empty_optional_variables_fall_back_to_their_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SENTRY_DSN", "")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "")
    settings = load_settings()
    assert (settings.sentry_dsn, settings.sentry_traces_sample_rate) == ("", 0.0)


# --- Phase 1: Supabase connection variables (docs/ENV_SETUP.md section 2) ---

FAKE_SECRET = "test-only-not-a-secret"  # noqa: S105  # explicit dummy value used to prove masking


@pytest.fixture
def required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")


@pytest.mark.usefixtures("required")
def test_supabase_variables_have_safe_defaults() -> None:
    settings = load_settings()
    assert settings.supabase_url == "http://supabase-kong:8000"
    assert settings.supabase_anon_key.get_secret_value() == ""
    assert settings.supabase_service_role_key.get_secret_value() == ""


@pytest.mark.usefixtures("required")
def test_supabase_variables_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-dummy")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-dummy")
    settings = load_settings()
    assert settings.supabase_url == "http://localhost:54321"
    assert settings.supabase_anon_key.get_secret_value() == "anon-dummy"
    assert settings.supabase_service_role_key.get_secret_value() == "service-dummy"


@pytest.mark.usefixtures("required")
def test_supabase_keys_never_appear_in_repr_str_or_dumps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_ANON_KEY", FAKE_SECRET)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", FAKE_SECRET + "-service")
    settings = load_settings()
    for rendered in (
        repr(settings),
        str(settings),
        settings.model_dump_json(),
        str(settings.model_dump()),
        repr(settings.supabase_anon_key),
        str(settings.supabase_service_role_key),
    ):
        assert FAKE_SECRET not in rendered


@pytest.mark.usefixtures("required")
@pytest.mark.parametrize(
    "bad_url", ["ftp://supabase", "http://supabase-kong:8000/", "http://supabase kong", "kong:8000"]
)
def test_invalid_supabase_url_names_the_variable_without_echoing_the_value(
    monkeypatch: pytest.MonkeyPatch, bad_url: str
) -> None:
    monkeypatch.setenv("SUPABASE_URL", bad_url)
    with pytest.raises(ConfigError) as error:
        load_settings()
    assert "SUPABASE_URL" in str(error.value)
    assert bad_url not in str(error.value)


@pytest.mark.usefixtures("required")
def test_empty_supabase_variables_fall_back_to_their_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    settings = load_settings()
    assert settings.supabase_url == "http://supabase-kong:8000"
    assert settings.supabase_anon_key.get_secret_value() == ""
    assert settings.supabase_service_role_key.get_secret_value() == ""


# --- Phase 2: JWT verification, Redis, site URL, first administrator (ENV_SETUP 2 and 7.5) ---


@pytest.mark.usefixtures("required")
def test_phase_2_variables_have_safe_defaults() -> None:
    settings = load_settings()
    # Empty secret and issuer: token verification then fails loudly instead of accepting anything.
    assert settings.supabase_jwt_secret.get_secret_value() == ""
    assert settings.supabase_jwt_issuer == ""
    assert settings.redis_url.get_secret_value() == "redis://redis:6379/0"
    assert settings.web_app_url == "http://localhost:3000"
    assert settings.first_admin_email == ""
    assert settings.first_admin_full_name == ""


@pytest.mark.usefixtures("required")
def test_phase_2_variables_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "jwt-dummy")
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "https://staging.example.test/auth/v1")
    monkeypatch.setenv("REDIS_URL", "rediss://:pw-dummy@cache.example.test:6379")
    monkeypatch.setenv("WEB_APP_URL", "https://staging.example.test")
    monkeypatch.setenv("FIRST_ADMIN_EMAIL", "first@example.test")
    monkeypatch.setenv("FIRST_ADMIN_FULL_NAME", "First Admin")
    settings = load_settings()
    assert settings.supabase_jwt_secret.get_secret_value() == "jwt-dummy"
    assert settings.supabase_jwt_issuer == "https://staging.example.test/auth/v1"
    assert settings.redis_url.get_secret_value() == "rediss://:pw-dummy@cache.example.test:6379"
    assert settings.web_app_url == "https://staging.example.test"
    assert settings.first_admin_email == "first@example.test"
    assert settings.first_admin_full_name == "First Admin"


@pytest.mark.usefixtures("required")
def test_the_jwt_secret_and_the_redis_url_never_appear_in_repr_str_or_dumps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwt_value = FAKE_SECRET + "-jwt"
    redis_value = "pw-" + FAKE_SECRET
    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_value)
    monkeypatch.setenv("REDIS_URL", f"redis://:{redis_value}@cache.example.test:6379")
    settings = load_settings()
    for rendered in (
        repr(settings),
        str(settings),
        settings.model_dump_json(),
        str(settings.model_dump()),
        repr(settings.supabase_jwt_secret),
        repr(settings.redis_url),
    ):
        assert jwt_value not in rendered
        assert redis_value not in rendered


@pytest.mark.usefixtures("required")
def test_secrets_are_not_echoed_when_another_variable_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", FAKE_SECRET + "-jwt")
    monkeypatch.setenv("REDIS_URL", f"redis://:{FAKE_SECRET}@cache.example.test:6379")
    monkeypatch.setenv("LOG_LEVEL", "nope")
    with pytest.raises(ConfigError) as error:
        load_settings()
    assert FAKE_SECRET not in str(error.value)


@pytest.mark.usefixtures("required")
@pytest.mark.parametrize(
    ("name", "bad_value"),
    [
        ("SUPABASE_JWT_ISSUER", "localhost:54321/auth/v1"),
        ("SUPABASE_JWT_ISSUER", "ftp://localhost/auth/v1"),
        ("SUPABASE_JWT_ISSUER", "http://local host/auth/v1"),
        ("WEB_APP_URL", "http://localhost:3000/"),
        ("WEB_APP_URL", "localhost:3000"),
        ("WEB_APP_URL", "http://local host"),
    ],
)
def test_invalid_urls_name_the_variable_without_echoing_the_value(
    monkeypatch: pytest.MonkeyPatch, name: str, bad_value: str
) -> None:
    monkeypatch.setenv(name, bad_value)
    with pytest.raises(ConfigError) as error:
        load_settings()
    assert name in str(error.value)
    assert bad_value not in str(error.value)


@pytest.mark.usefixtures("required")
def test_empty_phase_2_variables_fall_back_to_their_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("SUPABASE_JWT_SECRET", "SUPABASE_JWT_ISSUER", "REDIS_URL", "WEB_APP_URL"):
        monkeypatch.setenv(name, "")
    settings = load_settings()
    assert settings.supabase_jwt_issuer == ""
    assert settings.redis_url.get_secret_value() == "redis://redis:6379/0"
    assert settings.web_app_url == "http://localhost:3000"


# --- E2E test accounts (create_test_users): read by the CLI only, never by Settings ---


def _set_e2e(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for account in E2E_ACCOUNTS:
        values[f"E2E_{account}_EMAIL"] = f"e2e-{account.lower().replace('_', '-')}@example.test"
        values[f"E2E_{account}_PASSWORD"] = "pw-" + FAKE_SECRET + account
    values["E2E_INVITEE_EMAIL"] = "e2e-invitee@example.test"
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


def test_the_e2e_accounts_are_not_part_of_settings() -> None:
    assert not [name for name in Settings.model_fields if name.startswith("e2e")]


def test_the_e2e_accounts_load_from_the_eleven_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    values = _set_e2e(monkeypatch)
    accounts = load_e2e_accounts()
    for value in values.values():
        if "pw-" in value:
            assert value not in repr(accounts)
            assert value not in str(accounts)


def test_missing_e2e_variables_are_listed_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigError) as error:
        load_e2e_accounts()
    message = str(error.value)
    for account in E2E_ACCOUNTS:  # passwords have no default: each one must be named
        assert f"E2E_{account}_PASSWORD" in message


def test_a_short_e2e_password_is_refused_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weak = "Zq9xK2m"
    _set_e2e(monkeypatch, **{"E2E_RESET_PASSWORD": weak})
    with pytest.raises(ConfigError) as error:
        load_e2e_accounts()
    assert "E2E_RESET_PASSWORD" in str(error.value)
    assert weak not in str(error.value)


def test_a_bad_e2e_email_is_refused_without_echoing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_e2e(monkeypatch, E2E_ADMIN_EMAIL="not-an-email-value")
    with pytest.raises(ConfigError) as error:
        load_e2e_accounts()
    assert "E2E_ADMIN_EMAIL" in str(error.value)
    assert "not-an-email-value" not in str(error.value)


def test_e2e_passwords_are_never_in_an_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    values = _set_e2e(monkeypatch, E2E_ADMIN_EMAIL="not-an-email-value")
    with pytest.raises(ConfigError) as error:
        load_e2e_accounts()
    for name, value in values.items():
        if name.endswith("PASSWORD"):
            assert value not in str(error.value)

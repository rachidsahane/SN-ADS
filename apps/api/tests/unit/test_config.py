import pytest

from app.config import ConfigError, Settings, load_settings

ALL_VARIABLES = (
    "APP_ENV", "SERVICE_NAME", "APP_RELEASE", "LOG_LEVEL",
    "SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "MAX_UPLOAD_BYTES",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
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

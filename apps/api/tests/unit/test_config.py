import pytest

from app.config import ConfigError, Settings, load_settings

ALL_VARIABLES = (
    "APP_ENV", "SERVICE_NAME", "APP_RELEASE", "LOG_LEVEL",
    "SENTRY_DSN", "SENTRY_TRACES_SAMPLE_RATE", "MAX_UPLOAD_BYTES",
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

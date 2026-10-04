"""Application settings. The only module allowed to read environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ConfigError(Exception):
    """Raised at startup when the environment is incomplete or invalid."""


class Settings(BaseSettings):
    """Variables of the api and worker containers (docs/ENV_SETUP.md section 2)."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True)

    app_env: Literal["local", "staging", "production"]
    service_name: Literal["api", "worker"]
    app_release: str = Field(default="local", min_length=1, max_length=64)
    log_level: LogLevel = "INFO"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    max_upload_bytes: int = Field(default=10_485_760, ge=1)
    # Phase 1. Internal Kong address by default. The keys are SecretStr (never in a repr or a log)
    # and empty by default: the readiness probe then fails closed instead of breaking start-up.
    supabase_url: str = Field(default="http://supabase-kong:8000", pattern=r"^https?://[^\s/]+$")
    supabase_anon_key: SecretStr = SecretStr("")
    supabase_service_role_key: SecretStr = SecretStr("")
    # Phase 2. The JWT secret and the issuer are empty by default: verifying a token then raises a
    # ConfigError (loud 500) instead of ever accepting or refusing it by accident. The Redis URL
    # may carry a password (Upstash): SecretStr. `web_app_url` has no trailing slash.
    supabase_jwt_secret: SecretStr = SecretStr("")
    supabase_jwt_issuer: str = Field(default="", pattern=r"^$|^https?://[^\s/]+(/[^\s]*)?$")
    redis_url: SecretStr = SecretStr("redis://redis:6379/0")
    web_app_url: str = Field(default="http://localhost:3000", pattern=r"^https?://[^\s/]+$")
    first_admin_email: str = ""
    first_admin_full_name: str = ""
    # Demo: where the trained model files live (Docker named volume) and the seed CSV (cli only).
    model_dir: str = Field(default="/models", min_length=1, max_length=255)
    seed_csv_path: str = Field(default="", max_length=255)
    # Demo: file where `demo_accounts` keeps the generated passwords (cli only, git-ignored).
    demo_accounts_path: str = Field(default="", max_length=255)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _describe(error: ValidationError) -> str:
    """List the faulty variables by name; never echo a value (it may be a secret)."""
    problems = sorted(
        {
            f"{str(item['loc'][0]).upper() if item['loc'] else 'SETTINGS'} ({item['msg']})"
            for item in error.errors(include_input=False, include_url=False)
        }
    )
    return "Invalid configuration. Fix these environment variables: " + "; ".join(problems) + "."


_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class E2ETestAccounts(BaseSettings):
    """Local Playwright accounts (docs/ENV_SETUP.md 7.5). Read by `app.cli.create_test_users` only:
    the api and the worker never carry these variables, so they are not part of `Settings`.
    Passwords have no default; the generator of `make env-local` fills them in the root `.env`."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True)

    e2e_admin_email: str = Field(default="e2e-admin@example.test", pattern=_EMAIL_PATTERN)
    e2e_admin_password: SecretStr = Field(min_length=10)
    e2e_admin2_email: str = Field(default="e2e-admin2@example.test", pattern=_EMAIL_PATTERN)
    e2e_admin2_password: SecretStr = Field(min_length=10)
    e2e_marketer_a_email: str = Field(default="e2e-marketer-a@example.test", pattern=_EMAIL_PATTERN)
    e2e_marketer_a_password: SecretStr = Field(min_length=10)
    e2e_marketer_b_email: str = Field(default="e2e-marketer-b@example.test", pattern=_EMAIL_PATTERN)
    e2e_marketer_b_password: SecretStr = Field(min_length=10)
    e2e_reset_email: str = Field(default="e2e-reset@example.test", pattern=_EMAIL_PATTERN)
    e2e_reset_password: SecretStr = Field(min_length=10)
    e2e_invitee_email: str = Field(default="e2e-invitee@example.test", pattern=_EMAIL_PATTERN)

    def credentials(self, account: str) -> tuple[str, str]:
        """(email, password) of an account key such as `ADMIN` or `MARKETER_A`."""
        key = account.lower()
        email: str = getattr(self, f"e2e_{key}_email")
        password: SecretStr = getattr(self, f"e2e_{key}_password")
        return email, password.get_secret_value()


def load_e2e_accounts() -> E2ETestAccounts:
    """Read the eleven E2E_* variables, or fail with the NAMES of the faulty ones."""
    try:
        return E2ETestAccounts()
    except ValidationError as error:
        raise ConfigError(_describe(error)) from None


def load_settings() -> Settings:
    """Read and validate the environment, or fail with the list of faulty variables."""
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigError(_describe(error)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()

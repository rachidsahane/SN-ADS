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


def load_settings() -> Settings:
    """Read and validate the environment, or fail with the list of faulty variables."""
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigError(_describe(error)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()

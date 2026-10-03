"""Shared helpers for the deploy/supabase tests (stdlib + PyYAML, which the toolbox ships via pre-commit).

Everything here is read-only against the repository: tests that need a writable tree build it in a
temporary directory.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
STACK_DIR = REPO_ROOT / "deploy" / "supabase"
STACK_COMPOSE = STACK_DIR / "docker-compose.yml"
ROOT_COMPOSE = REPO_ROOT / "docker-compose.yml"
KONG_YML = STACK_DIR / "kong.yml"
ENV_EXAMPLE = STACK_DIR / ".env.example"
GENERATE_KEYS = STACK_DIR / "generate_keys.py"

# Variables of the stack that must be generated (never committed with a real value).
SECRET_VARIABLES = (
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
    "ANON_KEY",
    "SERVICE_ROLE_KEY",
    "PG_META_CRYPTO_KEY",
    "S3_PROTOCOL_ACCESS_KEY_ID",
    "S3_PROTOCOL_ACCESS_KEY_SECRET",
)

# Spec phase 1, 2.A.2: the complete content of deploy/supabase/.env.example (placeholders only).
EXAMPLE_VARIABLES: dict[str, str] = {
    "POSTGRES_PASSWORD": "change-me",
    "JWT_SECRET": "change-me",
    "ANON_KEY": "change-me",
    "SERVICE_ROLE_KEY": "change-me",
    "PG_META_CRYPTO_KEY": "change-me",
    "S3_PROTOCOL_ACCESS_KEY_ID": "change-me",
    "S3_PROTOCOL_ACCESS_KEY_SECRET": "change-me",
    "SUPABASE_PUBLIC_URL": "http://localhost:54321",
    "API_EXTERNAL_URL": "http://localhost:54321",
    "SITE_URL": "http://localhost:3000",
    "ADDITIONAL_REDIRECT_URLS": "http://localhost:3000/auth/confirm",
    "GOTRUE_JWT_EXP": "3600",
    "SMTP_HOST": "mailpit",
    "SMTP_PORT": "1025",
    "SMTP_USER": "",
    "SMTP_PASS": "",
    "SMTP_ADMIN_EMAIL": "no-reply@example.test",
    "SMTP_SENDER_NAME": "Soro Nua Campaign Predictor",
    "STORAGE_FILE_SIZE_LIMIT": "10485760",
    "KONG_HTTP_PORT": "54321",
    "KONG_BIND_ADDRESS": "127.0.0.1",
    "STUDIO_HOST_PORT": "54323",
}


def parse_env_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines (comments and blank lines ignored, optional surrounding quotes removed)."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def parse_env_file(path: Path) -> dict[str, str]:
    return parse_env_text(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    """Load a YAML file; a missing file is a test failure (red: implementation not written yet)."""
    if not path.is_file():
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} is missing (phase 1 implementation not written yet)")
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def environment_of(service: dict[str, Any]) -> dict[str, str]:
    """Normalise a compose `environment:` (mapping or list of KEY=VALUE) to a dict of strings."""
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {str(k): "" if v is None else str(v) for k, v in env.items()}
    out: dict[str, str] = {}
    for item in env:
        key, _, value = str(item).partition("=")
        out[key] = value
    return out


COMPOSE_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:?[-?+][^}]*)?\}")

"""Generate the secrets of the local Supabase stack (phase 1; the AWS modes arrive in phase 17).

Usage (from the repository root, inside the toolbox):

    python deploy/supabase/generate_keys.py --env local [--rotate]

What it does:
- reads `deploy/supabase/.env.example` (the list of variables, with placeholders);
- writes or completes `deploy/supabase/.env` (git-ignored, mode 600): a value that is absent,
  empty or `change-me` is generated, a real value is kept, so running twice changes nothing;
- `--rotate` regenerates every secret and re-signs ANON_KEY and SERVICE_ROLE_KEY;
- copies SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY and POSTGRES_PASSWORD into the ROOT `.env`
  (line by line: the other lines, the comments and the order are preserved).

The script never prints a value, only the NAMES of the variables it generated or kept.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

PLACEHOLDER = "change-me"
MIN_QUOTED_LENGTH = 2
ALPHANUMERIC = string.ascii_letters + string.digits
TEN_YEARS = 10 * 365 * 24 * 3600

STACK_DIR = Path(__file__).resolve().parent
ROOT_DIR = STACK_DIR.parents[1]
EXAMPLE_FILE = STACK_DIR / ".env.example"
STACK_ENV_FILE = STACK_DIR / ".env"
ROOT_ENV_FILE = ROOT_DIR / ".env"

# Root variable -> stack variable (the root compose file is interpolated from the root .env).
ROOT_SYNC = {
    "SUPABASE_ANON_KEY": "ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY": "SERVICE_ROLE_KEY",
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
}


def alphanumeric(length: int) -> str:
    return "".join(secrets.choice(ALPHANUMERIC) for _ in range(length))


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def sign_jwt(role: str, jwt_secret: str) -> str:
    """HS256 JWT `{role, iss: supabase, iat, exp: now + 10 years}` signed with `jwt_secret`."""
    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(
        json.dumps(
            {"role": role, "iss": "supabase", "iat": now, "exp": now + TEN_YEARS},
            separators=(",", ":"),
        ).encode()
    )
    signature = hmac.new(
        jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{b64url(signature)}"


def jwt_is_valid(token: str, role: str, jwt_secret: str) -> bool:
    """True when `token` is an HS256 JWT of `role` signed with `jwt_secret` (else re-signed)."""
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(
            jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        claims = json.loads(b64url_decode(payload))
        return (
            hmac.compare_digest(expected, b64url_decode(signature)) and claims.get("role") == role
        )
    except (ValueError, TypeError):
        return False


# Secrets drawn at random, and the two keys signed with JWT_SECRET (variable -> JWT role).
# POSTGRES_PASSWORD is embedded in a connection URL: alphanumeric only.
PLAIN_SECRETS: dict[str, Callable[[], str]] = {
    "POSTGRES_PASSWORD": lambda: alphanumeric(40),
    "JWT_SECRET": lambda: alphanumeric(64),
    "PG_META_CRYPTO_KEY": lambda: alphanumeric(32),
    "S3_PROTOCOL_ACCESS_KEY_ID": lambda: secrets.token_hex(16),
    "S3_PROTOCOL_ACCESS_KEY_SECRET": lambda: secrets.token_hex(32),
}
SIGNED_KEYS = {"ANON_KEY": "anon", "SERVICE_ROLE_KEY": "service_role"}
SECRET_NAMES = frozenset((*PLAIN_SECRETS, *SIGNED_KEYS))


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= MIN_QUOTED_LENGTH and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def is_placeholder(value: str | None) -> bool:
    return value in (None, "", PLACEHOLDER)


def build_stack_values(
    example: dict[str, str], existing: dict[str, str], rotate: bool
) -> tuple[dict[str, str], list[str], list[str]]:
    """Return (values, generated secret names, kept secret names) for the example's variables."""
    values = dict(example)
    generated: list[str] = []
    kept: list[str] = []

    def settle(name: str, make: Callable[[], str], *, force: bool = False) -> None:
        current = existing.get(name)
        if force or current is None or is_placeholder(current):
            values[name] = make()
            generated.append(name)
        else:
            values[name] = current
            kept.append(name)

    for name, make in PLAIN_SECRETS.items():
        if name in example:
            settle(name, make, force=rotate)

    jwt_secret = values.get("JWT_SECRET", "")
    for name, role in SIGNED_KEYS.items():
        if name in example:
            current = existing.get(name)
            stale = (
                current is not None
                and not is_placeholder(current)
                and not jwt_is_valid(current, role, jwt_secret)
            )
            settle(name, partial(sign_jwt, role, jwt_secret), force=rotate or stale)

    # Every other variable: a real existing value wins over the example value.
    for name in example:
        if name not in SECRET_NAMES and existing.get(name):
            values[name] = existing[name]
    return values, generated, kept


def render_stack_env(example_text: str, values: dict[str, str], existing: dict[str, str]) -> str:
    """Re-emit the example (comments and order kept) with final values, then unknown ones."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in example_text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            name = line.partition("=")[0].strip()
            out.append(f"{name}={values[name]}")
            seen.add(name)
        else:
            out.append(raw)
    extras = [f"{name}={value}" for name, value in existing.items() if name not in seen]
    if extras:
        out += ["", "# --- variables kept from the previous file ---", *extras]
    return "\n".join(out) + "\n"


def write_private(path: Path, text: str) -> None:
    """Write `text` to `path` with mode 600, even if the file pre-exists looser."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        os.chmod(path, 0o600)
        return
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def sync_root_env(path: Path, values: dict[str, str]) -> str:
    """Update or append the synchronised variables in the root .env; return the new text."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    pending = {
        root_name: values[stack_name]
        for root_name, stack_name in ROOT_SYNC.items()
        if stack_name in values
    }
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.partition("=")[0].strip()
        if name in pending:
            lines[index] = f"{name}={pending.pop(name)}"
    lines += [f"{name}={value}" for name, value in pending.items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the secrets of the Supabase stack.")
    parser.add_argument("--env", required=True, choices=("local", "staging", "production"))
    parser.add_argument(
        "--rotate", action="store_true", help="regenerate every secret and re-sign the keys"
    )
    args = parser.parse_args(argv)

    if args.env != "local":
        print(
            "generate_keys: the AWS modes (staging, production) arrive in phase 17.",
            file=sys.stderr,
        )
        return 2
    if not EXAMPLE_FILE.is_file():
        print("generate_keys: deploy/supabase/.env.example is missing.", file=sys.stderr)
        return 1

    example_text = EXAMPLE_FILE.read_text(encoding="utf-8")
    example = parse_env(example_text)
    existing = (
        parse_env(STACK_ENV_FILE.read_text(encoding="utf-8")) if STACK_ENV_FILE.exists() else {}
    )

    values, generated, kept = build_stack_values(example, existing, args.rotate)
    write_private(STACK_ENV_FILE, render_stack_env(example_text, values, existing))

    root_text = sync_root_env(ROOT_ENV_FILE, values)
    if not ROOT_ENV_FILE.exists() or ROOT_ENV_FILE.read_text(encoding="utf-8") != root_text:
        ROOT_ENV_FILE.write_text(root_text, encoding="utf-8")
        os.chmod(ROOT_ENV_FILE, 0o600)

    print("generate_keys: deploy/supabase/.env is ready (values are never printed).")
    print("  generated: " + (", ".join(generated) or "nothing"))
    print("  kept:      " + (", ".join(kept) or "nothing"))
    print("  synchronised in .env: " + ", ".join(ROOT_SYNC))
    if args.rotate:
        print("  rotation done: run `make db-reset` (the database password lives in its volume).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

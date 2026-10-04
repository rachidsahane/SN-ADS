"""Create (or reset) the two demo accounts: an administrator and a marketer. Idempotent.

    python -m app.cli.demo_accounts     # make demo

The passwords are generated once and kept in DEMO_ACCOUNTS_PATH (`.demo-accounts.txt` on the host,
git-ignored); a later run reuses them. Refused in production. The file is the only place where the
passwords appear; this command prints account names, never passwords.
"""

import secrets
import sys
from pathlib import Path
from typing import Final, TextIO

from supabase import Client

from app.cli._common import GOTRUE_ERRORS, describe_failure, find_profile
from app.config import ConfigError, get_settings
from app.infra.observability import capture, init_observability
from app.infra.supabase_clients import get_service_client

# (role, e-mail, full name). The administrator comes first (guard_last_admin).
ACCOUNTS: Final = (
    ("admin", "demo-admin@example.test", "Demo Admin"),
    ("marketer", "demo-marketer@example.test", "Demo Marketer"),
)
EXIT_OK = 0
EXIT_FAILURE = 1


def read_passwords(path: Path) -> dict[str, str]:
    """`role  email  password` lines of an existing file, as {email: password}."""
    if not path.exists():
        return {}
    rows = (line.split() for line in path.read_text().splitlines())
    return {row[1]: row[2] for row in rows if len(row) == 3 and "@" in row[1]}  # noqa: PLR2004


def write_passwords(path: Path, passwords: dict[str, str]) -> None:
    lines = ["Demo accounts (local only, never commit this file)  role / e-mail / password"]
    lines += [f"{role:<9} {email} {passwords[email]}" for role, email, _ in ACCOUNTS]
    path.write_text("\n".join(lines) + "\n")


def ensure_account(client: Client, role: str, email: str, name: str, password: str) -> str:
    profile = find_profile(client, email)
    if profile is None:
        created = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": name},
            }
        )
        if created.user is None:
            raise ConfigError("The authentication service did not return the created user.")
        user_id, state = str(created.user.id), "created"
    else:
        user_id, state = str(profile["id"]), "reset"
        client.auth.admin.update_user_by_id(user_id, {"password": password, "email_confirm": True})
    client.table("profiles").update({"role": role, "is_active": True, "full_name": name}).eq(
        "id", user_id
    ).execute()
    return state


def main(*, client: Client | None = None, out: TextIO | None = None) -> int:
    out = out or sys.stdout
    try:
        settings = get_settings()
        if settings.is_production:
            print("demo_accounts: refused in production.", file=out)
            return EXIT_FAILURE
        if not settings.demo_accounts_path:
            print("DEMO_ACCOUNTS_PATH is not set (docker compose mounts the file).", file=out)
            return EXIT_FAILURE
        path = Path(settings.demo_accounts_path)
        known = read_passwords(path)
        passwords = {
            email: known.get(email) or secrets.token_urlsafe(12) for _, email, _ in ACCOUNTS
        }
        write_passwords(path, passwords)  # first, so a failure below never loses a password
        service = client or get_service_client(settings)
        for role, email, name in ACCOUNTS:
            print(
                f"{role}: {ensure_account(service, role, email, name, passwords[email])}", file=out
            )
    except (*GOTRUE_ERRORS, ConfigError) as error:
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    except Exception as error:  # last resort: one line, reported with context
        capture(error, command="demo_accounts")
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    init_observability(get_settings())
    raise SystemExit(main())

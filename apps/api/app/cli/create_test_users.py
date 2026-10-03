"""Create or reset the local Playwright accounts (LLD 2, SECURITY_NOTES SEC-18). Idempotent.

    python -m app.cli.create_test_users            # make test-users

Refused in production before any network call. Existing accounts get their password reset at
every run, their role and name restored and are re-activated; the pending invitee is invited
(again) unless the invitation was already accepted. Names of accounts are printed, never values.
"""

import sys
from typing import Final, TextIO

from supabase import Client

from app.cli._common import (
    GOTRUE_ERRORS,
    describe_failure,
    find_profile,
    invite_options,
    is_confirmed,
)
from app.config import ConfigError, E2ETestAccounts, get_settings, load_e2e_accounts
from app.infra.observability import capture, init_observability
from app.infra.supabase_clients import get_service_client

# (variable prefix, role, full name). Administrators first: the database refuses to demote or
# deactivate the last active administrator (guard_last_admin), which a drifted account could hit.
ACCOUNTS: Final = (
    ("ADMIN", "admin", "E2E Admin"),
    ("ADMIN2", "admin", "E2E Admin Two"),
    ("MARKETER_A", "marketer", "E2E Marketer A"),
    ("MARKETER_B", "marketer", "E2E Marketer B"),
    ("RESET", "marketer", "E2E Reset User"),
)
INVITEE_NAME: Final = "E2E Invitee"
EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1


def _ensure_account(
    client: Client, key: str, role: str, full_name: str, accounts: E2ETestAccounts
) -> str:
    email, secret = accounts.credentials(key)
    profile = find_profile(client, email)
    admin = client.auth.admin
    if profile is None:
        created = admin.create_user(
            {
                "email": email,
                "password": secret,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            }
        )
        if created.user is None:
            raise ConfigError("The authentication service did not return the created user.")
        user_id, state = str(created.user.id), "created"
    else:
        user_id, state = str(profile["id"]), "reset"
        admin.update_user_by_id(user_id, {"password": secret, "email_confirm": True})
    client.table("profiles").update({"role": role, "is_active": True, "full_name": full_name}).eq(
        "id", user_id
    ).execute()
    return state


def _ensure_invitee(client: Client, email: str, web_app_url: str) -> str:
    profile = find_profile(client, email)
    if profile is not None and is_confirmed(client, profile["id"]):
        return "left alone"
    client.auth.admin.invite_user_by_email(email, invite_options(INVITEE_NAME, web_app_url))  # type: ignore[arg-type]
    return "invited" if profile is None else "invited again"


def main(
    argv: list[str] | None = None,
    *,
    client: Client | None = None,
    out: TextIO | None = None,
) -> int:
    out = out or sys.stdout
    if argv:
        print("create_test_users takes no argument.", file=out)
        return EXIT_FAILURE
    try:
        settings = get_settings()
        if settings.is_production:
            print("create_test_users: refused in production.", file=out)
            return EXIT_FAILURE
        accounts = load_e2e_accounts()
        service = client or get_service_client(settings)
        for key, role, full_name in ACCOUNTS:
            print(
                f"E2E_{key}: {_ensure_account(service, key, role, full_name, accounts)}", file=out
            )
        invitee = _ensure_invitee(service, accounts.e2e_invitee_email, settings.web_app_url)
        print(f"E2E_INVITEE: {invitee}", file=out)
    except (*GOTRUE_ERRORS, ConfigError) as error:
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    except Exception as error:  # last resort: one line, reported with context
        capture(error, command="create_test_users")
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    init_observability(get_settings())
    raise SystemExit(main())

"""Create or re-invite the first administrator (LLD 2, ENV_SETUP 7.4). Idempotent.

    python -m app.cli.bootstrap_admin --email a@b.test --full-name "Name" [--print-link]

The account is created through the gotrue admin API (an invitation e-mail is sent) and promoted to
`admin` with the service-role client: the only way to get an administrator without one. With
`--print-link` no e-mail is sent and the single-use link is printed for the operator only (it goes
to the output, never to the logs).
"""

import argparse
import re
import sys
import unicodedata
from typing import Any, Final, TextIO

from supabase import Client

from app.cli._common import (
    GOTRUE_ERRORS,
    describe_failure,
    find_profile,
    invite_options,
    is_confirmed,
)
from app.config import ConfigError, Settings, get_settings
from app.infra.observability import capture, init_observability
from app.infra.supabase_clients import get_service_client

MAX_EMAIL_LENGTH: Final = 254
MAX_NAME_LENGTH: Final = 120
_EMAIL: Final = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1
EXIT_USAGE: Final = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bootstrap_admin", description="Create or re-invite the first administrator."
    )
    parser.add_argument("--email", help="e-mail address (default: FIRST_ADMIN_EMAIL)")
    parser.add_argument("--full-name", help="display name (default: FIRST_ADMIN_FULL_NAME)")
    parser.add_argument(
        "--print-link",
        action="store_true",
        help="send no e-mail: print the single-use invitation link instead",
    )
    return parser


def _validate(email: str, full_name: str) -> tuple[str, str] | str:
    """(clean e-mail, clean name) or the reason why the input is refused."""
    email = email.strip().lower()
    full_name = full_name.strip()
    if not email or len(email) > MAX_EMAIL_LENGTH or not _EMAIL.match(email):
        return "A valid e-mail address is required (--email or FIRST_ADMIN_EMAIL)."
    if not full_name or len(full_name) > MAX_NAME_LENGTH:
        return (
            "A full name of 1 to 120 characters is required (--full-name or FIRST_ADMIN_FULL_NAME)."
        )
    if any(unicodedata.category(character).startswith("C") for character in full_name):
        return "The full name must not contain control characters."
    return email, full_name


class _Bootstrap:
    def __init__(
        self, client: Client, settings: Settings, out: TextIO, *, print_link: bool
    ) -> None:
        self.client = client
        self.settings = settings
        self.out = out
        self.print_link = print_link
        self.link: str | None = None

    def say(self, line: str) -> None:
        print(line, file=self.out)

    def run(self, email: str, full_name: str) -> int:
        profile = find_profile(self.client, email)
        if profile is None:
            self._set_admin(self._invite(email, full_name))
            self._announce(f"Invitation sent to {email}. Open the mailbox to read it.", email)
            return EXIT_OK
        if not profile["is_active"]:
            self.say("The account is deactivated. Reactivate it before bootstrapping.")
            return EXIT_FAILURE
        if is_confirmed(self.client, profile["id"]):
            if profile["role"] == "admin":
                self.say(f"{email} is already an active administrator. Nothing to do.")
            else:
                self._set_admin(profile["id"])
                self.say(f"{email} is now an administrator.")
            return EXIT_OK
        self._invite(email, full_name)
        if profile["role"] != "admin":
            self._set_admin(profile["id"])
        self._announce(f"Invitation sent again to {email}.", email)
        return EXIT_OK

    def _invite(self, email: str, full_name: str) -> str:
        """Send the invitation e-mail, or (print mode) only prepare the single-use link.
        Returns the id of the invited user."""
        options = invite_options(full_name, self.settings.web_app_url)
        admin = self.client.auth.admin
        if self.print_link:
            params: Any = {"type": "invite", "email": email, "options": options}
            response = admin.generate_link(params)
            token_hash = response.properties.hashed_token
            self.link = (
                f"{self.settings.web_app_url}/auth/confirm?token_hash={token_hash}"
                "&type=invite&next=/auth/set-password"
            )
            return str(response.user.id)
        invited = admin.invite_user_by_email(email, options)  # type: ignore[arg-type]
        if invited.user is None:
            raise ConfigError("The authentication service did not return the invited user.")
        return str(invited.user.id)

    def _set_admin(self, user_id: str) -> None:
        self.client.table("profiles").update({"role": "admin"}).eq("id", user_id).execute()

    def _announce(self, line: str, email: str) -> None:
        if self.link is None:
            self.say(line)
            return
        self.say(f"Invitation link created for {email}. No e-mail was sent.")
        self.say(self.link)
        self.say("This link is single-use, do not share it.")


def main(
    argv: list[str] | None = None,
    *,
    client: Client | None = None,
    out: TextIO | None = None,
) -> int:
    out = out or sys.stdout
    args = _parser().parse_args(argv)  # a usage error exits with status 2 (argparse)
    try:
        settings = get_settings()
        checked = _validate(
            args.email if args.email is not None else settings.first_admin_email,
            args.full_name if args.full_name is not None else settings.first_admin_full_name,
        )
        if isinstance(checked, str):
            print(checked, file=out)
            return EXIT_USAGE
        service = client or get_service_client(settings)
        return _Bootstrap(service, settings, out, print_link=args.print_link).run(*checked)
    except (*GOTRUE_ERRORS, ConfigError) as error:
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    except Exception as error:  # last resort: one line, reported with context
        capture(error, command="bootstrap_admin")
        print(describe_failure(error), file=out)
        return EXIT_FAILURE


if __name__ == "__main__":
    init_observability(get_settings())
    raise SystemExit(main())

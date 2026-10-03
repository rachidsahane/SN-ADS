"""Helpers shared by the operations commands (service-role client, gotrue admin API).

Every command prints one plain English line per outcome: no traceback, no key, no response body.
"""

import uuid
from typing import Any, Final

import httpx
from supabase import AuthApiError, AuthError, Client, PostgrestAPIError

from app.config import ConfigError

DATABASE_ERRORS: Final = (httpx.HTTPError, PostgrestAPIError)
GOTRUE_ERRORS: Final = (AuthError, *DATABASE_ERRORS)
INVITE_METADATA_KEY: Final = "full_name"


def invite_options(full_name: str, web_app_url: str) -> dict[str, Any]:
    """Metadata copied to the profile by the database trigger, and the page that opens the link."""
    return {"data": {INVITE_METADATA_KEY: full_name}, "redirect_to": f"{web_app_url}/auth/confirm"}


def find_profile(client: Client, email: str) -> dict[str, Any] | None:
    """`id, role, is_active` of the profile with this e-mail (service client: bypasses RLS)."""
    rows = (
        client.table("profiles")
        .select("id,role,is_active")
        .eq("email", email)
        .limit(1)
        .execute()
        .data
    )
    return dict(rows[0]) if rows else None


def is_confirmed(client: Client, user_id: str | uuid.UUID) -> bool:
    """True once the user opened the invitation link (`email_confirmed_at` is set)."""
    user = client.auth.admin.get_user_by_id(str(user_id)).user
    return user is not None and user.email_confirmed_at is not None


def describe_failure(error: Exception) -> str:
    """One line for the operator. Only the status and the error CODE are shown, never a message."""
    if isinstance(error, AuthApiError):
        hint = ""
        if error.status >= 500:  # noqa: PLR2004
            hint = " Check that the stack is healthy (web serves the e-mail templates)."
        return (
            f"The authentication service refused the request (status {error.status}, "
            f"code {error.code}).{hint}"
        )
    if isinstance(error, AuthError):
        return "The authentication service answered with an error."
    if isinstance(error, PostgrestAPIError):
        return f"The database refused the change (code {error.code})."
    if isinstance(error, httpx.HTTPError):
        return "The Supabase stack is not reachable. Run 'make up' and try again."
    if isinstance(error, ConfigError):
        return str(error)
    return "Unexpected error. See the logs."

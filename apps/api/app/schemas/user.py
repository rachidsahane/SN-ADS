"""The profile of a user, the body of GET /api/v1/me and the authenticated caller."""

import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StrictBool, StringConstraints

AppRole = Literal["marketer", "admin"]
UserStatus = Literal["invited", "active", "deactivated"]


class Profile(BaseModel):
    """One row of `public.profiles` (docs/DATA_MODEL.md section 4.1)."""

    id: uuid.UUID
    email: str
    full_name: str
    role: AppRole
    is_active: bool


class MeResponse(Profile):
    """Body of GET /api/v1/me (API_SPEC 6.2): exactly these five fields."""

    model_config = ConfigDict(extra="forbid")


class ProfileRecord(Profile):
    """A profile row read with its creation date (administration of users)."""

    created_at: datetime


class AdminUser(ProfileRecord):
    """One user as the administrator sees it (API_SPEC 6.6): the profile, its date and status."""

    status: UserStatus


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    next_cursor: str | None


# Same pattern as cli/bootstrap_admin and config.py.
EMAIL_PATTERN: Final = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
FULL_NAME_MAX_LENGTH: Final = 120


def _no_control_character(value: str) -> str:
    """Refuse control, format and other "C*" characters (newlines, zero-width, bidi overrides)."""
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("control characters are not allowed")
    return value


Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=254,
        pattern=EMAIL_PATTERN,
    ),
]
FullName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=FULL_NAME_MAX_LENGTH),
    AfterValidator(_no_control_character),
]


class InviteUserRequest(BaseModel):
    """Body of POST /api/v1/admin/users/invite: nothing is guessed, all three fields are given."""

    model_config = ConfigDict(extra="forbid", strict=True)

    email: Email
    full_name: FullName
    role: AppRole


class UpdateUserRequest(BaseModel):
    """Body of PATCH /api/v1/admin/users/{id}. An explicit null counts as "not provided"; the
    service refuses a request that carries nothing."""

    model_config = ConfigDict(extra="forbid", strict=True)

    role: AppRole | None = None
    is_active: StrictBool | None = None
    full_name: FullName | None = None


@dataclass(frozen=True)
class CurrentUser:
    """Who is calling. The token is kept to query the database as the user (RLS applies)."""

    id: uuid.UUID
    role: AppRole
    access_token: str = field(repr=False)

"""The profile of a user, the body of GET /api/v1/me and the authenticated caller."""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

AppRole = Literal["marketer", "admin"]


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


@dataclass(frozen=True)
class CurrentUser:
    """Who is calling. The token is kept to query the database as the user (RLS applies)."""

    id: uuid.UUID
    role: AppRole
    access_token: str = field(repr=False)

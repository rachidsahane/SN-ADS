"""schemas/user.py: the shapes of the profile, of GET /api/v1/me and of the authenticated user."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.user import CurrentUser, MeResponse, Profile

FIELDS = {"id", "email", "full_name", "role", "is_active"}


def _values() -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "email": "awa@example.test",
        "full_name": "Awa N.",
        "role": "marketer",
        "is_active": True,
    }


def test_the_profile_has_exactly_the_five_fields() -> None:
    assert set(Profile.model_fields) == FIELDS


def test_the_me_response_has_exactly_the_five_documented_fields() -> None:
    assert set(MeResponse.model_fields) == FIELDS
    assert set(MeResponse(**_values()).model_dump(mode="json")) == FIELDS  # type: ignore[arg-type]


def test_the_me_response_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MeResponse(**_values(), is_superuser=True)  # type: ignore[arg-type, call-arg]


@pytest.mark.parametrize("role", ["superuser", "", "ADMIN"])
def test_the_role_is_a_closed_choice(role: str) -> None:
    with pytest.raises(ValidationError):
        Profile(**{**_values(), "role": role})  # type: ignore[arg-type]


def test_the_current_user_never_shows_its_token_in_a_repr() -> None:
    token = "user-token-" + uuid.uuid4().hex
    user = CurrentUser(id=uuid.uuid4(), role="admin", access_token=token)
    assert token not in repr(user)
    assert token not in str(user)
    assert user.access_token == token


def test_the_current_user_is_immutable() -> None:
    user = CurrentUser(id=uuid.uuid4(), role="admin", access_token="x")  # noqa: S106
    with pytest.raises(AttributeError):
        user.role = "marketer"  # type: ignore[misc]

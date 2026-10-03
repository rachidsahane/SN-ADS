"""schemas/user.py: the shapes of the profile, of GET /api/v1/me and of the authenticated user."""

import uuid
from datetime import UTC, datetime
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.schemas.audit import AuditAction, AuditEntry, AuditLogPage, AuditTargetType
from app.schemas.user import (
    AdminUser,
    AdminUserPage,
    CurrentUser,
    InviteUserRequest,
    MeResponse,
    Profile,
    ProfileRecord,
    UpdateUserRequest,
)

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


# --- phase 3: administration of users (API_SPEC 6.6) -------------------------------------------

ADMIN_USER_FIELDS = {"id", "email", "full_name", "role", "is_active", "status", "created_at"}
CREATED = datetime(2026, 10, 3, 14, 5, 0, 123456, tzinfo=UTC)


def _admin_user(**changes: object) -> dict[str, object]:
    return {**_values(), "status": "active", "created_at": CREATED, **changes}


def _invite(**changes: object) -> dict[str, object]:
    return {"email": "awa@example.test", "full_name": "Awa N.", "role": "marketer", **changes}


def _error_types(error: ValidationError) -> list[tuple[str, str]]:
    return [(str(e["loc"][-1]), e["type"]) for e in error.errors()]


def test_a_profile_record_is_a_profile_with_its_creation_date() -> None:
    assert set(ProfileRecord.model_fields) == FIELDS | {"created_at"}
    assert issubclass(ProfileRecord, Profile)


def test_an_admin_user_has_exactly_the_seven_documented_fields() -> None:
    assert set(AdminUser.model_fields) == ADMIN_USER_FIELDS
    dumped = AdminUser(**_admin_user()).model_dump(mode="json")  # type: ignore[arg-type]
    assert set(dumped) == ADMIN_USER_FIELDS
    assert dumped["created_at"] == "2026-10-03T14:05:00.123456Z"


@pytest.mark.parametrize("status", ["invited", "active", "deactivated"])
def test_the_status_accepts_its_three_values(status: str) -> None:
    assert AdminUser(**_admin_user(status=status)).status == status  # type: ignore[arg-type]


@pytest.mark.parametrize("status", ["pending", "ACTIVE", "", "disabled"])
def test_the_status_is_a_closed_choice(status: str) -> None:
    with pytest.raises(ValidationError):
        AdminUser(**_admin_user(status=status))  # type: ignore[arg-type]


def test_a_page_of_users_has_items_and_a_next_cursor() -> None:
    assert set(AdminUserPage.model_fields) == {"items", "next_cursor"}
    page = AdminUserPage(items=[AdminUser(**_admin_user())], next_cursor=None)  # type: ignore[arg-type]
    assert page.model_dump(mode="json")["next_cursor"] is None


def test_the_invitation_lowercases_and_strips_the_email_and_strips_the_name() -> None:
    request = InviteUserRequest(**_invite(email="  Awa.N@Example.TEST ", full_name="  Awa N.  "))  # type: ignore[arg-type]
    assert (request.email, request.full_name, request.role) == (
        "awa.n@example.test",
        "Awa N.",
        "marketer",
    )


def test_the_invitation_email_is_254_characters_at_most() -> None:
    longest = "a" * 241 + "@example.test"
    assert len(longest) == 254
    assert InviteUserRequest(**_invite(email=longest)).email == longest  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(email="a" + longest))  # type: ignore[arg-type]
    assert _error_types(error.value) == [("email", "string_too_long")]


@pytest.mark.parametrize(
    "email", ["", "no-at-sign", "a@b", "a b@example.test", "@example.test", "ab"]
)
def test_an_invalid_invitation_email_is_refused(email: str) -> None:
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(email=email))  # type: ignore[arg-type]
    assert {field for field, _ in _error_types(error.value)} == {"email"}


def test_the_invitation_email_pattern_error_is_reported_as_a_pattern_mismatch() -> None:
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(email="no-at-sign"))  # type: ignore[arg-type]
    assert _error_types(error.value) == [("email", "string_pattern_mismatch")]


def test_the_invitation_requires_the_three_fields_and_guesses_nothing() -> None:
    for missing in ("email", "full_name", "role"):
        values = _invite()
        del values[missing]
        with pytest.raises(ValidationError) as error:
            InviteUserRequest(**values)  # type: ignore[arg-type]
        assert _error_types(error.value) == [(missing, "missing")]


def test_the_invitation_refuses_unknown_fields_such_as_a_status() -> None:
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(is_active=False))  # type: ignore[arg-type]
    assert _error_types(error.value) == [("is_active", "extra_forbidden")]


@pytest.mark.parametrize("role", ["owner", "ADMIN", "", "superuser", None])
def test_the_invitation_role_is_a_closed_choice(role: object) -> None:
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(role=role))  # type: ignore[arg-type]
    assert {field for field, _ in _error_types(error.value)} == {"role"}


@pytest.mark.parametrize("role", ["marketer", "admin"])
def test_the_invitation_accepts_both_roles(role: str) -> None:
    assert InviteUserRequest(**_invite(role=role)).role == role  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name", ["", "   ", "x" * 121, "Awa\x00N", "Awa\nN", "Awa\tN", "Awa\u200bN", "Awa\u202eN"]
)
def test_an_invalid_full_name_is_refused(name: str) -> None:
    with pytest.raises(ValidationError) as error:
        InviteUserRequest(**_invite(full_name=name))  # type: ignore[arg-type]
    assert {field for field, _ in _error_types(error.value)} == {"full_name"}


def test_a_full_name_of_1_to_120_characters_is_accepted() -> None:
    assert InviteUserRequest(**_invite(full_name="A")).full_name == "A"  # type: ignore[arg-type]
    assert len(InviteUserRequest(**_invite(full_name="é" * 120)).full_name) == 120  # type: ignore[arg-type]


def test_a_markup_looking_name_is_kept_as_text() -> None:
    hostile = "<img src=x onerror=alert(1)>"
    assert InviteUserRequest(**_invite(full_name=hostile)).full_name == hostile  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [{"role": "admin"}, {"is_active": False}, {"is_active": True}, {"full_name": "New Name"}],
)
def test_an_update_accepts_each_field_alone(field: dict[str, Any]) -> None:
    request = UpdateUserRequest(**field)
    assert request.model_dump(exclude_none=True) == field


def test_an_update_with_nothing_is_valid_for_the_schema_and_refused_by_the_service() -> None:
    """An explicit null counts as "not provided" (the service answers 422 for an empty change)."""
    assert UpdateUserRequest().model_dump(exclude_none=True) == {}
    assert (
        UpdateUserRequest(role=None, is_active=None, full_name=None).model_dump(exclude_none=True)
        == {}
    )


@pytest.mark.parametrize("value", ["false", "true", 0, 1, "yes"])
def test_the_activity_flag_is_strictly_a_boolean(value: object) -> None:
    with pytest.raises(ValidationError) as error:
        UpdateUserRequest(is_active=value)  # type: ignore[arg-type]
    assert {field for field, _ in _error_types(error.value)} == {"is_active"}


def test_an_update_refuses_unknown_fields_and_a_bad_role_or_name() -> None:
    for bad in (
        {"email": "x@y.test"},
        {"id": str(uuid.uuid4())},
        {"role": "owner"},
        {"full_name": ""},
    ):
        with pytest.raises(ValidationError):
            UpdateUserRequest(**bad)  # type: ignore[arg-type]


# --- phase 3: audit log (API_SPEC 6.9, DATA_MODEL 4.6) -----------------------------------------


def _entry(**changes: object) -> dict[str, object]:
    return {
        "id": 7,
        "created_at": CREATED,
        "actor": {"id": uuid.uuid4(), "full_name": "Boss Admin"},
        "action": "user.invited",
        "target_type": "user",
        "target_id": str(uuid.uuid4()),
        "metadata": {"email": "awa@example.test", "role": "marketer"},
        **changes,
    }


def test_the_audit_actions_are_the_ten_of_the_data_model() -> None:
    assert set(get_args(AuditAction)) == {
        "user.invited",
        "user.role_changed",
        "user.deactivated",
        "user.reactivated",
        "upload.accepted",
        "upload.failed",
        "model.training_requested",
        "model.training_succeeded",
        "model.training_failed",
        "model.activated",
    }
    assert set(get_args(AuditTargetType)) == {"user", "upload", "model_version"}


def test_an_audit_entry_has_the_documented_fields() -> None:
    assert set(AuditEntry.model_fields) == {
        "id", "created_at", "actor", "action", "target_type", "target_id", "metadata"
    }  # fmt: skip
    assert set(AuditLogPage.model_fields) == {"items", "next_cursor"}


def test_an_entry_without_actor_is_serialised_with_a_null_actor() -> None:
    dumped = AuditEntry(**_entry(actor=None)).model_dump(mode="json")  # type: ignore[arg-type]
    assert "actor" in dumped
    assert dumped["actor"] is None


def test_an_entry_with_an_actor_shows_only_its_id_and_name() -> None:
    dumped = AuditEntry(**_entry()).model_dump(mode="json")  # type: ignore[arg-type]
    assert set(dumped["actor"]) == {"id", "full_name"}


@pytest.mark.parametrize("changes", [{"action": "user.deleted"}, {"target_type": "campaign"}])
def test_an_entry_refuses_an_unknown_action_or_target_type(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AuditEntry(**_entry(**changes))  # type: ignore[arg-type]


def test_an_audit_page_serialises_with_a_cursor_or_null() -> None:
    page = AuditLogPage(items=[AuditEntry(**_entry())], next_cursor="abc")  # type: ignore[arg-type]
    assert page.model_dump(mode="json")["next_cursor"] == "abc"

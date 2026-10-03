"""services/user_admin_service.py: list, invite, change role, deactivate and reactivate users.

Doubles: `FakeServiceClient` is the gotrue admin API (patched in as the service client of the
module), `FakeUserDb` is the Supabase client built with the ADMIN's token (profiles, audit log and
the database rules), `ProfileCache` runs over a `FakeRedis`. `world.events` is the ordered log of
every side effect, so that the order of effects of D-085 can be asserted.
"""

import uuid
from typing import Any, cast

import httpx
import pytest
import redis
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError
from supabase import Client

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.infra.observability import configure_logging
from app.infra.pagination import Cursor, Page, decode_cursor
from app.infra.profile_cache import CachedProfile
from app.schemas.user import AdminUser, InviteUserRequest, UpdateUserRequest
from app.services import user_admin_service
from app.services.user_admin_service import (
    BAN_DURATION,
    UNBAN_DURATION,
    invite_user,
    list_users,
    update_user,
)
from tests.support import WEB_APP_URL, AdminWorld, FakeUser, make_admin_world, reported_errors

EMAIL = "awa.invitee@example.test"
NAME = "Awa Invitee"
TARGET_EMAIL = "target.person@example.test"
TARGET_NAME = "Target Person"
UNAVAILABLE = "The service is temporarily unavailable. Please try again in a few minutes."
LAST_ADMIN = "At least one active administrator is required."
LAST_ADMIN_ERROR = APIError({"message": "LAST_ADMIN", "code": "P0001", "details": "", "hint": ""})
DATABASE_ERROR = APIError({"message": "boom", "code": "XX000", "details": "", "hint": ""})
GOTRUE_500 = AuthApiError("boom", 500, "unexpected_failure")  # type: ignore[arg-type]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> AdminWorld:
    built = make_admin_world()
    monkeypatch.setattr(user_admin_service, "get_service_client", lambda *_a, **_k: built.service)
    return built


@pytest.fixture(autouse=True)
def logging_to_stdout(settings: Settings) -> None:
    configure_logging(settings)


def _db(world: AdminWorld) -> Client:
    return cast(Client, world.db)


def _page(limit: int = 50, after: Cursor | None = None) -> Page:
    return Page(limit=limit, after=after)


def _list(world: AdminWorld, settings: Settings, **page: Any) -> Any:
    return list_users(_db(world), settings=settings, page=_page(**page))


def _invite(world: AdminWorld, settings: Settings, **changes: Any) -> AdminUser:
    values = {"email": EMAIL, "full_name": NAME, "role": "marketer", **changes}
    return invite_user(world.actor, _db(world), InviteUserRequest(**values), settings=settings)


def _target(world: AdminWorld, **changes: Any) -> FakeUser:
    return world.service.seed(TARGET_EMAIL, full_name=TARGET_NAME, **changes)


def _update(
    world: AdminWorld, settings: Settings, who: str | uuid.UUID, **fields: Any
) -> AdminUser:
    return update_user(
        world.actor,
        _db(world),
        uuid.UUID(str(who)),
        UpdateUserRequest(**fields),
        settings=settings,
        cache=world.cache,
    )


def _refusal(call: Any) -> AppError:
    with pytest.raises(AppError) as error:
        call()
    return error.value


def _audit_actions(world: AdminWorld) -> list[str]:
    return [entry["action"] for entry in world.db.audit]


# ================================================================================================
# list_users
# ================================================================================================


def test_each_user_gets_its_status_and_a_deactivated_user_is_never_invited(
    world: AdminWorld, settings: Settings
) -> None:
    world.service.seed("active@example.test", confirmed=True)
    world.service.seed("invited@example.test", confirmed=False)
    world.service.seed("off@example.test", confirmed=True, is_active=False)
    world.service.seed("offinvited@example.test", confirmed=False, is_active=False)
    page = _list(world, settings)
    assert {user.email: user.status for user in page.items} == {
        world.admin.email: "active",
        "active@example.test": "active",
        "invited@example.test": "invited",
        "off@example.test": "deactivated",
        "offinvited@example.test": "deactivated",
    }


def test_the_listing_is_newest_first_with_the_documented_fields(
    world: AdminWorld, settings: Settings
) -> None:
    world.service.seed("one@example.test")
    world.service.seed("two@example.test")
    page = _list(world, settings)
    assert all(isinstance(user, AdminUser) for user in page.items)
    assert [user.email for user in page.items] == [
        "two@example.test",
        "one@example.test",
        world.admin.email,
    ]
    assert page.next_cursor is None
    assert page.items[0].created_at > page.items[1].created_at


def test_the_listing_reads_the_profiles_with_the_admin_client_one_row_more_than_the_limit(
    world: AdminWorld, settings: Settings
) -> None:
    _list(world, settings, limit=7)
    (_, sent) = world.db.calls_named("profiles.select")[-1]
    assert sent["limit"] == 8
    assert sent["orders"] == [("created_at", True), ("id", True)]
    assert sent["columns"] == "id,email,full_name,role,is_active,created_at"
    assert world.service.calls_named("profile_update") == []


def test_a_cursor_is_given_only_when_more_rows_exist_and_leads_to_the_rest(
    world: AdminWorld, settings: Settings
) -> None:
    world.service.seed("one@example.test")
    world.service.seed("two@example.test")
    first = _list(world, settings, limit=2)
    assert [user.email for user in first.items] == ["two@example.test", "one@example.test"]
    assert first.next_cursor is not None
    last = first.items[-1]
    assert decode_cursor(first.next_cursor) == Cursor(
        created_at=last.created_at.isoformat(), id=str(last.id)
    )
    second = _list(world, settings, limit=2, after=decode_cursor(first.next_cursor))
    assert [user.email for user in second.items] == [world.admin.email]
    assert second.next_cursor is None


def test_exactly_the_limit_of_rows_has_no_cursor(world: AdminWorld, settings: Settings) -> None:
    world.service.seed("one@example.test")
    page = _list(world, settings, limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is None


def test_confirmation_dates_are_read_page_after_page_until_an_empty_page(
    world: AdminWorld, settings: Settings
) -> None:
    for number in range(399):
        world.service.seed(f"bulk{number}@example.test", confirmed=True)
    page = _list(world, settings, limit=100)
    assert {user.status for user in page.items} == {"active"}
    asked = world.service.calls_named("gotrue_list")
    assert [(call[1], call[2]) for call in asked] == [(1, 200), (2, 200), (3, 200)]  # 3rd is empty


def test_a_server_side_cap_on_per_page_does_not_turn_confirmed_users_into_invited(
    world: AdminWorld, settings: Settings
) -> None:
    """gotrue may return fewer than `per_page` on a page that is not the last: only an EMPTY page
    ends the loop (A3)."""
    world.service.list_users_cap = 50
    for number in range(119):
        world.service.seed(f"bulk{number}@example.test", confirmed=True)
    page = _list(world, settings, limit=100)
    assert len(page.items) == 100
    assert {user.status for user in page.items} == {"active"}
    assert [call[1] for call in world.service.calls_named("gotrue_list")] == [1, 2, 3, 4]


@pytest.mark.parametrize(
    "failure", [GOTRUE_500, httpx.ConnectError("down")], ids=["gotrue", "network"]
)
def test_a_gotrue_failure_on_the_listing_is_a_503_reported_without_personal_data(
    world: AdminWorld,
    settings: Settings,
    failure: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:
    world.service.errors["list_users"] = failure
    refusal = _refusal(lambda: _list(world, settings))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.SERVICE_UNAVAILABLE,
        503,
        UNAVAILABLE,
    )
    out = capsys.readouterr().out
    assert len(reported_errors(out)) == 1
    assert world.admin.email not in out


def test_a_database_failure_on_the_listing_is_a_503(world: AdminWorld, settings: Settings) -> None:
    world.db.errors["profiles.select"] = DATABASE_ERROR
    refusal = _refusal(lambda: _list(world, settings))
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)


# ================================================================================================
# invite_user
# ================================================================================================


@pytest.mark.parametrize(
    "state",
    [{"confirmed": True}, {"confirmed": False}, {"confirmed": True, "is_active": False}],
    ids=["active", "invited", "deactivated"],
)
def test_an_existing_profile_in_any_state_is_a_409_and_gotrue_is_never_called(
    world: AdminWorld, settings: Settings, state: dict[str, Any]
) -> None:
    world.service.seed(EMAIL, **state)
    refusal = _refusal(lambda: _invite(world, settings, email=EMAIL.upper()))
    assert (refusal.code, refusal.status) == (ErrorCode.EMAIL_ALREADY_REGISTERED, 409)
    assert refusal.message == "A user with this email already exists."
    assert world.service.calls_named("invite") == []
    assert world.events == []


@pytest.mark.parametrize(
    "change",
    [{"role": "marketer"}, {"is_active": False}],
    ids=["demoted", "deactivated"],
)
def test_an_actor_who_is_no_longer_an_active_admin_in_the_database_cannot_invite(
    world: AdminWorld, settings: Settings, change: dict[str, Any]
) -> None:
    """The profile cache may still say "admin" (60 s, or a failed invalidation). The invitation is
    sent with the SERVICE key, so the database (RLS) must confirm the actor first."""
    world.service.profiles[world.admin.id].update(change)
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status) == (ErrorCode.FORBIDDEN, 403)
    assert world.service.calls_named("invite") == []
    assert world.events == []


def test_the_invitation_goes_to_gotrue_with_the_name_and_the_confirm_page(
    world: AdminWorld, settings: Settings
) -> None:
    created = _invite(world, settings, email="Awa.Invitee@Example.TEST")
    ((_, email, options),) = world.service.calls_named("invite")
    assert email == EMAIL
    assert options == {"data": {"full_name": NAME}, "redirect_to": f"{WEB_APP_URL}/auth/confirm"}
    assert (created.email, created.full_name) == (EMAIL, NAME)


def test_a_marketer_invitation_returns_the_invited_user_and_changes_no_role(
    world: AdminWorld, settings: Settings
) -> None:
    created = _invite(world, settings)
    assert isinstance(created, AdminUser)
    assert (created.role, created.status, created.is_active) == ("marketer", "invited", True)
    assert str(created.id) == world.service.user_by_email(EMAIL).id  # type: ignore[union-attr]
    assert world.db.calls_named("profiles.update") == []
    assert world.service.calls_named("profile_update") == []


def test_an_admin_invitation_promotes_with_the_admins_token_never_the_service_client(
    world: AdminWorld, settings: Settings
) -> None:
    created = _invite(world, settings, role="admin")
    assert created.role == "admin"
    assert world.db.calls_named("profiles.update") == [
        ("profiles.update", str(created.id), {"role": "admin"})
    ]
    assert (
        world.service.calls_named("profile_update") == []
    )  # the role never goes through gotrue metadata
    ((_, _, options),) = world.service.calls_named("invite")
    assert "role" not in options["data"]


def test_the_audit_entry_is_written_after_the_effects(
    world: AdminWorld, settings: Settings
) -> None:
    created = _invite(world, settings, role="admin")
    assert world.events == ["invite", "db.update", "audit"]
    (entry,) = world.db.audit
    assert (entry["action"], entry["target_type"], entry["target_id"]) == (
        "user.invited",
        "user",
        str(created.id),
    )
    assert entry["actor_id"] == world.admin.id
    assert entry["metadata"] == {"email": EMAIL, "role": "admin"}


def test_a_marketer_invitation_audit_metadata(world: AdminWorld, settings: Settings) -> None:
    _invite(world, settings)
    assert world.events == ["invite", "audit"]
    assert world.db.audit[0]["metadata"] == {"email": EMAIL, "role": "marketer"}


def test_a_race_on_the_email_is_a_409(world: AdminWorld, settings: Settings) -> None:
    world.service.errors["invite_user_by_email"] = AuthApiError(  # type: ignore[arg-type]
        "A user with this email address exists", 422, "email_exists"
    )
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status) == (ErrorCode.EMAIL_ALREADY_REGISTERED, 409)
    assert world.events == []


@pytest.mark.parametrize("code", ["validation_failed", "email_address_invalid"])
def test_an_address_gotrue_refuses_is_a_422_on_the_email_not_a_reported_503(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str], code: str
) -> None:
    """Our pattern is looser than gotrue's parser (`a,b@c.d`, `ab@c..d`, accents...): the typo is
    the administrator's to fix, not an outage to report."""
    world.service.errors["invite_user_by_email"] = AuthApiError(  # type: ignore[arg-type]
        "Unable to validate email address: invalid format", 400, code
    )
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.VALIDATION_ERROR,
        422,
        "Some fields are invalid.",
    )
    assert [(d.field, d.issue) for d in refusal.details] == [("email", "invalid_format")]
    assert EMAIL not in repr(refusal.details)
    assert reported_errors(capsys.readouterr().out) == []
    assert world.service.calls_named("delete_user") == []
    assert world.events == []


def test_gotrue_rate_limit_is_a_429_with_retry_after(world: AdminWorld, settings: Settings) -> None:
    world.service.errors["invite_user_by_email"] = AuthApiError(  # type: ignore[arg-type]
        "email rate limit exceeded", 429, "over_email_send_rate_limit"
    )
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status) == (ErrorCode.RATE_LIMITED, 429)
    assert refusal.message == "Too many requests. Please wait a moment."
    assert refusal.headers == {"Retry-After": "60"}
    assert world.service.calls_named("delete_user") == []
    assert world.db.audit == []


def test_a_gotrue_5xx_after_the_user_was_created_rolls_the_invitation_back(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    world.service.late_errors["invite_user_by_email"] = GOTRUE_500
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.SERVICE_UNAVAILABLE,
        503,
        UNAVAILABLE,
    )
    assert len(world.service.calls_named("delete_user")) == 1
    assert world.service.user_by_email(EMAIL) is None  # nothing is left behind
    assert world.db.audit == []
    out = capsys.readouterr().out
    assert len(reported_errors(out)) == 1
    assert EMAIL not in out


def test_a_network_failure_before_anything_was_created_is_a_503_with_nothing_to_roll_back(
    world: AdminWorld, settings: Settings
) -> None:
    world.service.errors["invite_user_by_email"] = httpx.ConnectError("down")
    refusal = _refusal(lambda: _invite(world, settings))
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    assert world.service.calls_named("delete_user") == []
    assert world.db.audit == []


def test_a_failed_promotion_rolls_the_invitation_back_and_writes_no_audit(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    world.db.errors["profiles.update"] = DATABASE_ERROR
    refusal = _refusal(lambda: _invite(world, settings, role="admin"))
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    assert len(world.service.calls_named("delete_user")) == 1
    assert world.service.user_by_email(EMAIL) is None
    assert world.db.audit == []
    assert EMAIL not in capsys.readouterr().out


def test_a_promotion_that_changed_no_row_is_a_failure_too(
    world: AdminWorld, settings: Settings
) -> None:
    world.db.vanish_on_update = True
    refusal = _refusal(lambda: _invite(world, settings, role="admin"))
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    assert len(world.service.calls_named("delete_user")) == 1
    assert world.db.audit == []


def test_a_failed_rollback_is_only_reported_and_the_503_is_still_returned(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    world.db.errors["profiles.update"] = DATABASE_ERROR
    world.service.errors["delete_user"] = GOTRUE_500
    refusal = _refusal(lambda: _invite(world, settings, role="admin"))
    assert (refusal.code, refusal.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    out = capsys.readouterr().out
    assert reported_errors(out)
    assert EMAIL not in out


def test_a_failed_audit_write_does_not_undo_or_fail_the_invitation(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    world.db.errors["rpc.log_audit"] = httpx.ConnectError("down")
    created = _invite(world, settings)
    assert created.status == "invited"
    assert world.service.calls_named("delete_user") == []
    assert world.service.user_by_email(EMAIL) is not None
    (reported,) = reported_errors(capsys.readouterr().out)
    assert reported["operation"] == "audit_write"


# ================================================================================================
# update_user: validation, self, unknown
# ================================================================================================


@pytest.mark.parametrize("fields", [{}, {"role": None, "is_active": None, "full_name": None}])
def test_an_update_without_any_field_is_a_422(
    world: AdminWorld, settings: Settings, fields: dict[str, Any]
) -> None:
    target = _target(world)
    refusal = _refusal(lambda: _update(world, settings, target.id, **fields))
    assert (refusal.code, refusal.status) == (ErrorCode.VALIDATION_ERROR, 422)
    assert refusal.message == "Some fields are invalid."
    (detail,) = refusal.details
    assert (detail.field, detail.issue) == ("body", "required")
    assert detail.message == "Provide at least one field to update: role, is_active or full_name."
    assert world.events == []


@pytest.mark.parametrize(
    "fields",
    [
        {"role": "marketer"},
        {"is_active": False},
        {"full_name": "New Name"},
        {"role": "admin", "is_active": True},
    ],
    ids=["role", "is_active", "full_name", "several"],
)
def test_any_change_to_the_own_account_is_a_409_and_nothing_is_touched(
    world: AdminWorld, settings: Settings, fields: dict[str, Any]
) -> None:
    refusal = _refusal(lambda: _update(world, settings, world.admin.id, **fields))
    assert (refusal.code, refusal.status) == (ErrorCode.SELF_ACTION_FORBIDDEN, 409)
    assert refusal.message == "You cannot change your own account."
    assert world.db.calls == []  # not even a read
    assert world.service.calls == []
    assert world.redis.calls == []
    assert world.events == []


def test_an_unknown_user_is_a_404_and_nothing_is_written(
    world: AdminWorld, settings: Settings
) -> None:
    refusal = _refusal(lambda: _update(world, settings, uuid.uuid4(), role="admin"))
    assert (refusal.code, refusal.status) == (ErrorCode.NOT_FOUND, 404)
    assert refusal.message == "User not found."
    assert world.events == []
    assert world.redis.calls == []
    assert world.db.calls_named("profiles.update") == []


# ================================================================================================
# update_user: effects
# ================================================================================================


def test_a_role_change_writes_the_role_only_clears_the_cache_and_is_audited(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world)
    world.cache.set(uuid.UUID(target.id), CachedProfile("marketer", True))
    result = _update(world, settings, target.id, role="admin")
    assert isinstance(result, AdminUser)
    assert (str(result.id), result.role, result.status, result.is_active) == (
        target.id,
        "admin",
        "active",
        True,
    )
    assert world.db.calls_named("profiles.update") == [
        ("profiles.update", target.id, {"role": "admin"})
    ]
    assert world.cache.get(uuid.UUID(target.id)) is None  # effective at once, not after 60 s
    assert world.service.calls_named("ban") == []
    (entry,) = world.db.audit
    assert (entry["action"], entry["target_type"], entry["target_id"]) == (
        "user.role_changed",
        "user",
        target.id,
    )
    assert entry["actor_id"] == world.admin.id
    assert entry["metadata"] == {"email": TARGET_EMAIL, "from": "marketer", "to": "admin"}
    assert world.events == ["db.update", "cache.invalidate", "audit"]


def test_the_status_of_a_still_invited_user_is_invited_after_a_role_change(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world, confirmed=False)
    assert _update(world, settings, target.id, role="admin").status == "invited"


def test_the_same_role_is_a_no_op_without_write_audit_or_cache_call(
    world: AdminWorld, settings: Settings
) -> None:
    """Only an EFFECTIVE role change clears the cache; a request that carries `is_active` always
    does (a retry must be able to repair a half-done deactivation, see the tests below)."""
    target = _target(world, role="marketer")
    result = _update(world, settings, target.id, role="marketer")
    assert (result.role, result.status) == ("marketer", "active")
    assert world.db.calls_named("profiles.update") == []
    assert world.db.audit == []
    assert world.redis.calls == []
    assert world.events == []


def test_a_name_change_is_written_without_audit_ban_or_cache_call(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world)
    result = _update(world, settings, target.id, full_name="  New Name ")
    assert result.full_name == "New Name"
    assert world.db.calls_named("profiles.update") == [
        ("profiles.update", target.id, {"full_name": "New Name"})
    ]
    assert world.db.audit == []
    assert world.service.calls_named("ban") == []
    assert world.redis.calls == []


def test_a_deactivation_writes_the_flag_bans_in_gotrue_then_clears_the_cache_then_audits(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world)
    world.cache.set(uuid.UUID(target.id), CachedProfile("marketer", True))
    result = _update(world, settings, target.id, is_active=False)
    assert (result.status, result.is_active) == ("deactivated", False)
    assert world.db.calls_named("profiles.update") == [
        ("profiles.update", target.id, {"is_active": False})
    ]
    assert BAN_DURATION == "876000h"
    assert world.service.calls_named("ban") == [("ban", target.id, "876000h")]
    assert world.cache.get(uuid.UUID(target.id)) is None
    assert world.events == ["db.update", "ban", "cache.invalidate", "audit"]
    (entry,) = world.db.audit
    assert (entry["action"], entry["target_id"]) == ("user.deactivated", target.id)
    assert entry["metadata"] == {"email": TARGET_EMAIL}


def test_a_reactivation_writes_the_flag_lifts_the_ban_then_clears_the_cache_then_audits(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world, is_active=False)
    result = _update(world, settings, target.id, is_active=True)
    assert (result.status, result.is_active) == ("active", True)
    assert UNBAN_DURATION == "none"
    assert world.service.calls_named("ban") == [("ban", target.id, "none")]
    assert world.events == ["db.update", "unban", "cache.invalidate", "audit"]
    (entry,) = world.db.audit
    assert (entry["action"], entry["target_id"]) == ("user.reactivated", target.id)
    assert entry["metadata"] == {"email": TARGET_EMAIL}


def test_a_reactivated_user_who_never_confirmed_is_invited_again(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world, is_active=False, confirmed=False)
    assert _update(world, settings, target.id, is_active=True).status == "invited"


def test_a_role_and_an_activity_change_are_one_statement_and_two_audit_entries(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world)
    _update(world, settings, target.id, role="admin", is_active=False)
    (write,) = world.db.calls_named(
        "profiles.update"
    )  # ONE statement: the trigger sees the final state
    assert write[2] == {"role": "admin", "is_active": False}
    assert _audit_actions(world) == ["user.role_changed", "user.deactivated"]
    assert world.events.count("db.update") == 1


def test_deactivating_an_already_inactive_user_repairs_the_ban_without_a_second_audit_entry(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world, is_active=False)
    result = _update(world, settings, target.id, is_active=False)
    assert result.status == "deactivated"
    assert world.db.calls_named("profiles.update") == []
    assert world.service.calls_named("ban") == [("ban", target.id, BAN_DURATION)]
    assert world.db.audit == []


def test_reactivating_an_already_active_user_re_applies_the_unban_without_audit(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world)
    _update(world, settings, target.id, is_active=True)
    assert world.service.calls_named("ban") == [("ban", target.id, "none")]
    assert world.db.calls_named("profiles.update") == []
    assert world.db.audit == []


# ================================================================================================
# update_user: failures
# ================================================================================================


def test_the_last_administrator_guard_is_a_409_and_nothing_else_happens(
    world: AdminWorld, settings: Settings
) -> None:
    target = _target(world, role="admin")
    world.db.errors["profiles.update"] = LAST_ADMIN_ERROR
    refusal = _refusal(lambda: _update(world, settings, target.id, is_active=False))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.LAST_ADMIN,
        409,
        LAST_ADMIN,
    )
    assert world.events == []  # no ban, no cache call, no audit
    assert world.service.calls_named("ban") == []
    assert world.redis.calls == []
    assert world.db.audit == []


def test_a_forbidden_error_of_the_database_is_a_403(world: AdminWorld, settings: Settings) -> None:
    target = _target(world)
    world.db.errors["profiles.update"] = APIError(
        {"message": "FORBIDDEN", "code": "P0001", "details": "", "hint": ""}
    )
    refusal = _refusal(lambda: _update(world, settings, target.id, role="admin"))
    assert (refusal.code, refusal.status) == (ErrorCode.FORBIDDEN, 403)


@pytest.mark.parametrize("stage", ["profiles.select", "profiles.update"])
@pytest.mark.parametrize(
    "failure", [DATABASE_ERROR, httpx.ConnectError("down")], ids=["database", "network"]
)
def test_a_database_outage_is_a_503_reported_without_personal_data(
    world: AdminWorld,
    settings: Settings,
    stage: str,
    failure: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _target(world)
    world.db.errors[stage] = failure
    refusal = _refusal(lambda: _update(world, settings, target.id, role="admin"))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.SERVICE_UNAVAILABLE,
        503,
        UNAVAILABLE,
    )
    out = capsys.readouterr().out
    assert len(reported_errors(out)) == 1
    assert TARGET_EMAIL not in out
    assert TARGET_NAME not in out
    assert world.events == []


def test_an_update_that_changed_no_row_is_a_404(world: AdminWorld, settings: Settings) -> None:
    target = _target(world)
    world.db.vanish_on_update = True
    refusal = _refusal(lambda: _update(world, settings, target.id, role="admin"))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.NOT_FOUND,
        404,
        "User not found.",
    )
    assert world.events == []


def test_a_failed_ban_still_clears_the_cache_and_audits_then_answers_503(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target(world)
    world.cache.set(uuid.UUID(target.id), CachedProfile("marketer", True))
    world.service.errors["update_user_by_id"] = GOTRUE_500
    refusal = _refusal(lambda: _update(world, settings, target.id, is_active=False))
    assert (refusal.code, refusal.status, refusal.message) == (
        ErrorCode.SERVICE_UNAVAILABLE,
        503,
        UNAVAILABLE,
    )
    assert world.service.profiles[target.id]["is_active"] is False  # the database flag did change
    assert world.cache.get(uuid.UUID(target.id)) is None
    assert _audit_actions(world) == ["user.deactivated"]
    assert world.events == ["db.update", "cache.invalidate", "audit"]
    out = capsys.readouterr().out
    assert len(reported_errors(out)) == 1
    assert TARGET_EMAIL not in out


def test_a_redis_failure_on_the_invalidation_is_reported_and_does_not_fail_the_request(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target(world)
    world.redis.error = redis.exceptions.ConnectionError("down")
    result = _update(world, settings, target.id, is_active=False)
    assert result.status == "deactivated"  # the 60 s TTL and RLS bound the stale window (D-085)
    assert world.service.calls_named("ban") == [("ban", target.id, BAN_DURATION)]
    assert _audit_actions(world) == ["user.deactivated"]
    (reported,) = reported_errors(capsys.readouterr().out)
    assert reported["operation"] == "invalidate_profile_cache"
    assert reported["user_id"] == target.id


def test_a_failed_status_lookup_falls_back_to_active_and_is_reported(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target(world, confirmed=False)
    world.service.errors["get_user_by_id"] = GOTRUE_500
    result = _update(world, settings, target.id, role="admin")
    assert result.status == "active"
    assert world.db.calls_named("profiles.update")  # the change itself was made
    assert len(reported_errors(capsys.readouterr().out)) == 1


def test_nothing_reported_ever_holds_an_email_a_name_or_the_token(
    world: AdminWorld, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _target(world)
    world.service.errors["update_user_by_id"] = GOTRUE_500
    world.redis.error = redis.exceptions.ConnectionError("down")
    world.db.errors["rpc.log_audit"] = httpx.ConnectError("down")
    _refusal(lambda: _update(world, settings, target.id, role="admin", is_active=False))
    out = capsys.readouterr().out
    assert reported_errors(out)
    for secret in (TARGET_EMAIL, TARGET_NAME, world.admin.email, "admin-token-value"):
        assert secret not in out

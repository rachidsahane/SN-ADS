"""repositories/profiles_repo.py: one profile by id, read with the client it is given.

The real supabase-py client talks to an in-process PostgREST, so the test proves the columns, the
filter and the credentials that go over the wire.
"""

import uuid
from datetime import UTC, datetime

import pytest
from postgrest.exceptions import APIError

from app.config import Settings
from app.infra.pagination import Cursor, keyset_filter
from app.infra.supabase_clients import get_user_client
from app.repositories.profiles_repo import (
    ADMIN_USER_COLUMNS,
    find_profile_by_email,
    get_profile,
    get_profile_record,
    list_profile_records,
    update_profile,
)
from app.schemas.user import Profile, ProfileRecord
from tests.support import ProfileServer


def test_it_returns_the_profile_of_the_user(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(
        user_id, email="awa@example.test", full_name="Awa N.", role="admin", is_active=True
    )
    db = get_user_client("user-token-value", auth_settings)
    assert get_profile(db, user_id) == Profile(
        id=user_id, email="awa@example.test", full_name="Awa N.", role="admin", is_active=True
    )


def test_it_returns_none_when_there_is_no_row(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    """RLS hides the rows of others and, for a deactivated user, the user's own row."""
    db = get_user_client("user-token-value", auth_settings)
    assert get_profile(db, uuid.uuid4()) is None


def test_it_selects_the_five_columns_and_filters_by_id(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    get_profile(get_user_client("user-token-value", auth_settings), user_id)
    (request,) = profile_server.requests
    assert request.path == "/rest/v1/profiles"
    assert request.query["select"] == ["id,email,full_name,role,is_active"]
    assert request.query["id"] == [f"eq.{user_id}"]
    assert request.query["limit"] == ["1"]


def test_it_uses_the_client_it_receives_and_never_the_service_key(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id)
    get_profile(get_user_client("user-token-value", auth_settings), user_id)
    (request,) = profile_server.requests
    assert request.headers["authorization"] == "Bearer user-token-value"
    service = auth_settings.supabase_service_role_key.get_secret_value()
    assert service not in request.headers.values()


# --- phase 3: the reads and the update behind the administration of users ----------------------

CREATED = "2026-10-03T10:00:05.123456+00:00"


def _db(settings: Settings, token: str = "admin-token-value") -> object:  # noqa: S107
    return get_user_client(token, settings)


def test_the_admin_user_columns_are_the_six_of_the_listing() -> None:
    assert ADMIN_USER_COLUMNS == "id,email,full_name,role,is_active,created_at"


def test_get_profile_record_adds_the_creation_date(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, email="awa@example.test", created_at=CREATED)
    record = get_profile_record(_db(auth_settings), user_id)  # type: ignore[arg-type]
    assert record == ProfileRecord(
        id=user_id,
        email="awa@example.test",
        full_name="Test Person",
        role="marketer",
        is_active=True,
        created_at=datetime(2026, 10, 3, 10, 0, 5, 123456, tzinfo=UTC),
    )
    (request,) = profile_server.requests
    assert request.query["select"] == [ADMIN_USER_COLUMNS]
    assert request.query["id"] == [f"eq.{user_id}"]


def test_get_profile_record_is_none_when_no_row_is_visible(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    assert get_profile_record(_db(auth_settings), uuid.uuid4()) is None  # type: ignore[arg-type]


def test_find_profile_by_email_filters_on_the_email_and_takes_one_row(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, email="awa@example.test", created_at=CREATED)
    profile_server.add_profile(uuid.uuid4(), email="other@example.test", created_at=CREATED)
    found = find_profile_by_email(_db(auth_settings), "awa@example.test")  # type: ignore[arg-type]
    assert found is not None
    assert found.id == user_id
    (request,) = profile_server.requests
    assert request.query["email"] == ["eq.awa@example.test"]
    assert request.query["limit"] == ["1"]
    assert find_profile_by_email(_db(auth_settings), "nobody@example.test") is None  # type: ignore[arg-type]


def test_a_listing_asks_for_newest_first_with_the_id_as_tie_break_and_a_limit(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    for number in range(3):
        profile_server.add_profile(
            uuid.uuid4(), email=f"u{number}@example.test", created_at=CREATED
        )
    records = list_profile_records(_db(auth_settings), limit=51, after=None)  # type: ignore[arg-type]
    assert len(records) == 3
    assert all(isinstance(record, ProfileRecord) for record in records)
    (request,) = profile_server.requests
    assert request.path == "/rest/v1/profiles"
    assert request.query["select"] == [ADMIN_USER_COLUMNS]
    assert ",".join(request.query["order"]) == "created_at.desc,id.desc"
    assert request.query["limit"] == ["51"]
    assert "or" not in request.query
    assert "id" not in request.query


def test_a_listing_after_a_cursor_sends_the_keyset_filter_and_nothing_else(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    cursor = Cursor(created_at=CREATED, id=str(uuid.uuid4()))
    list_profile_records(_db(auth_settings), limit=10, after=cursor)  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert request.query["or"] == [f"({keyset_filter(cursor)})"]  # '+' of the offset survives
    assert request.query["limit"] == ["10"]


def test_update_profile_sends_only_the_changes_for_that_id_and_returns_the_new_row(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, role="marketer", created_at=CREATED)
    updated = update_profile(_db(auth_settings), user_id, {"role": "admin"})  # type: ignore[arg-type]
    assert updated is not None
    assert (updated.id, updated.role) == (user_id, "admin")
    (request,) = profile_server.requests
    assert (request.method, request.path) == ("PATCH", "/rest/v1/profiles")
    assert request.query["id"] == [f"eq.{user_id}"]
    assert request.body == {"role": "admin"}
    assert "return=representation" in request.headers["prefer"]


def test_update_profile_with_several_changes_is_one_request(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, created_at=CREATED)
    update_profile(_db(auth_settings), user_id, {"role": "admin", "is_active": False})  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert request.body == {"role": "admin", "is_active": False}


def test_update_profile_is_none_when_the_database_changed_no_row(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    """RLS refusal (own row, not an admin) or a row that is gone: zero rows, no error."""
    profile_server.refuse_updates = True
    assert update_profile(_db(auth_settings), uuid.uuid4(), {"role": "admin"}) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("operation", ["list", "update", "find", "record"])
def test_a_database_error_is_not_swallowed_by_the_repository(
    auth_settings: Settings, profile_server: ProfileServer, operation: str
) -> None:
    profile_server.status = 500
    db = _db(auth_settings)
    calls = {
        "list": lambda: list_profile_records(db, limit=5, after=None),  # type: ignore[arg-type]
        "update": lambda: update_profile(db, uuid.uuid4(), {"role": "admin"}),  # type: ignore[arg-type]
        "find": lambda: find_profile_by_email(db, "a@example.test"),  # type: ignore[arg-type]
        "record": lambda: get_profile_record(db, uuid.uuid4()),  # type: ignore[arg-type]
    }
    with pytest.raises(APIError):
        calls[operation]()


def test_every_phase_3_read_and_write_carries_the_user_token_and_never_the_service_key(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    user_id = uuid.uuid4()
    profile_server.add_profile(user_id, created_at=CREATED)
    db = _db(auth_settings, "caller-token-value")
    list_profile_records(db, limit=5, after=None)  # type: ignore[arg-type]
    find_profile_by_email(db, "a@example.test")  # type: ignore[arg-type]
    get_profile_record(db, user_id)  # type: ignore[arg-type]
    update_profile(db, user_id, {"full_name": "New Name"})  # type: ignore[arg-type]
    service = auth_settings.supabase_service_role_key.get_secret_value()
    assert len(profile_server.requests) == 4
    for request in profile_server.requests:
        assert request.headers["authorization"] == "Bearer caller-token-value"
        assert service not in request.headers.values()

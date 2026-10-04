"""repositories/audit_repo.py: write through `log_audit`, read `audit_log` with the actor embed.

The real supabase-py client talks to an in-process PostgREST, so the test proves what goes over the
wire: the RPC and its four parameters, the select and its embed, the order, the limit, the keyset
filter, and the caller's own token.
"""

import uuid

import pytest
from postgrest.exceptions import APIError

from app.config import Settings
from app.infra.pagination import Cursor, keyset_filter
from app.infra.supabase_clients import get_user_client
from app.repositories.audit_repo import insert_system_entry, list_entries, log_action
from app.schemas.audit import AuditEntry
from tests.support import ProfileServer

ACTOR = uuid.uuid4()
TARGET = str(uuid.uuid4())
STAMP = "2026-10-03T10:00:05.123456+00:00"


def _db(settings: Settings, token: str = "admin-token-value") -> object:  # noqa: S107
    return get_user_client(token, settings)


def _row(**changes: object) -> dict[str, object]:
    return {
        "id": 7,
        "created_at": STAMP,
        "action": "user.invited",
        "target_type": "user",
        "target_id": TARGET,
        "metadata": {"email": "awa@example.test", "role": "marketer"},
        "actor": {"id": str(ACTOR), "full_name": "Boss Admin"},
        **changes,
    }


# --- log_action --------------------------------------------------------------------------------


def test_log_action_calls_the_log_audit_function_with_its_four_parameters(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    result = log_action(
        _db(auth_settings),  # type: ignore[arg-type]
        action="user.role_changed",
        target_type="user",
        target_id=TARGET,
        metadata={"email": "awa@example.test", "from": "marketer", "to": "admin"},
    )
    assert result is None
    (request,) = profile_server.requests
    assert (request.method, request.path) == ("POST", "/rest/v1/rpc/log_audit")
    assert request.body == {
        "p_action": "user.role_changed",
        "p_target_type": "user",
        "p_target_id": TARGET,
        "p_metadata": {"email": "awa@example.test", "from": "marketer", "to": "admin"},
    }


def test_log_action_uses_the_callers_token_and_never_the_service_key(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    log_action(
        _db(auth_settings, "caller-token-value"),  # type: ignore[arg-type]
        action="user.invited",
        target_type="user",
        target_id=TARGET,
        metadata={},
    )
    (request,) = profile_server.requests
    assert request.headers["authorization"] == "Bearer caller-token-value"
    assert (
        auth_settings.supabase_service_role_key.get_secret_value() not in request.headers.values()
    )


def test_log_action_does_not_swallow_a_database_error(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    profile_server.status = 400
    profile_server.error_body = {"code": "P0001", "message": "FORBIDDEN", "details": "", "hint": ""}
    with pytest.raises(APIError) as error:
        log_action(
            _db(auth_settings),  # type: ignore[arg-type]
            action="user.invited",
            target_type="user",
            target_id=TARGET,
            metadata={},
        )
    assert (error.value.code, error.value.message) == ("P0001", "FORBIDDEN")


# --- list_entries ------------------------------------------------------------------------------


def test_list_entries_selects_the_columns_and_the_actor_embed(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    list_entries(_db(auth_settings), limit=51, after=None)  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert request.path == "/rest/v1/audit_log"
    selected = request.query["select"][0]
    assert selected.startswith("id,created_at,action,target_type,target_id,metadata")
    assert "actor:" in selected  # the join on actor_id
    assert "(id,full_name)" in selected
    assert "email" not in selected


def test_list_entries_orders_newest_first_with_the_id_tie_break_and_limits(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    list_entries(_db(auth_settings), limit=51, after=None)  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert ",".join(request.query["order"]) == "created_at.desc,id.desc"
    assert request.query["limit"] == ["51"]
    assert "or" not in request.query


def test_list_entries_after_a_cursor_sends_the_keyset_filter(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    cursor = Cursor(created_at=STAMP, id="123")
    list_entries(_db(auth_settings), limit=10, after=cursor)  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert request.query["or"] == [f"({keyset_filter(cursor)})"]


def test_list_entries_maps_the_rows_including_a_missing_actor(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    profile_server.audit_rows = [_row(id=8, actor=None), _row()]
    entries = list_entries(_db(auth_settings), limit=10, after=None)  # type: ignore[arg-type]
    assert all(isinstance(entry, AuditEntry) for entry in entries)
    assert [entry.id for entry in entries] == [8, 7]
    assert entries[0].actor is None
    assert entries[1].actor is not None
    assert (entries[1].actor.id, entries[1].actor.full_name) == (ACTOR, "Boss Admin")
    assert entries[1].metadata == {"email": "awa@example.test", "role": "marketer"}


def test_list_entries_uses_the_callers_token_and_does_not_swallow_errors(
    auth_settings: Settings, profile_server: ProfileServer
) -> None:
    list_entries(_db(auth_settings, "caller-token-value"), limit=5, after=None)  # type: ignore[arg-type]
    (request,) = profile_server.requests
    assert request.headers["authorization"] == "Bearer caller-token-value"
    assert (
        auth_settings.supabase_service_role_key.get_secret_value() not in request.headers.values()
    )
    profile_server.status = 500
    with pytest.raises(APIError):
        list_entries(_db(auth_settings), limit=5, after=None)  # type: ignore[arg-type]


def test_a_system_entry_is_inserted_without_reading_it_back() -> None:
    """The service role may only insert into audit_log: the insert must not ask for the row back."""
    calls: list[tuple[dict[str, object], object]] = []

    class Table:
        def insert(self, row: dict[str, object], returning: object) -> "Table":
            calls.append((row, returning))
            return self

        def execute(self) -> None:
            return None

    class Db:
        def table(self, name: str) -> Table:
            assert name == "audit_log"
            return Table()

    insert_system_entry(Db(), {"action": "model.training_succeeded"})  # type: ignore[arg-type]
    ((row, returning),) = calls
    assert row == {"action": "model.training_succeeded"}
    assert str(returning) == "minimal"

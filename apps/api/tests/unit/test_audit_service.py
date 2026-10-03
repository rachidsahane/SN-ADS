"""services/audit_service.py: write an audit entry as the admin (never fails the action), list them.

`FakeUserDb` is the user-token client: it applies the rules of the database (`log_audit` admin
only, `audit_log` readable by admins, the actor embed).
"""

import uuid

import httpx
import pytest
from postgrest.exceptions import APIError

from app.api.errors import AppError, ErrorCode
from app.config import Settings
from app.infra.observability import configure_logging
from app.infra.pagination import Cursor, Page, decode_cursor
from app.schemas.audit import AuditLogPage
from app.services.audit_service import list_audit, record
from tests.support import AdminWorld, make_admin_world, reported_errors

UNAVAILABLE = "The service is temporarily unavailable. Please try again in a few minutes."
EMAIL = "private.person@example.test"


@pytest.fixture
def world() -> AdminWorld:
    return make_admin_world()


@pytest.fixture(autouse=True)
def logging_to_stdout(settings: Settings) -> None:
    configure_logging(settings)


def _record(world: AdminWorld, target_id: str | None = None) -> bool:
    return record(
        world.db,  # type: ignore[arg-type]
        action="user.invited",
        target_type="user",
        target_id=target_id or str(uuid.uuid4()),
        metadata={"email": EMAIL, "role": "marketer"},
    )


# --- record ------------------------------------------------------------------------------------


def test_record_writes_one_entry_as_the_admin_and_returns_true(world: AdminWorld) -> None:
    target = str(uuid.uuid4())
    assert _record(world, target) is True
    (entry,) = world.db.audit
    assert (entry["action"], entry["target_type"], entry["target_id"]) == (
        "user.invited",
        "user",
        target,
    )
    assert entry["actor_id"] == world.admin.id
    assert entry["metadata"] == {"email": EMAIL, "role": "marketer"}
    assert len(world.db.calls_named("rpc")) == 1


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("down"),
        httpx.ReadTimeout("slow"),
        APIError({"message": "boom", "code": "XX000", "details": "", "hint": ""}),
        APIError({"message": "FORBIDDEN", "code": "P0001", "details": "", "hint": ""}),
    ],
    ids=["connect", "timeout", "database", "forbidden"],
)
def test_a_failed_write_returns_false_and_is_reported_once_without_personal_data(
    world: AdminWorld, failure: Exception, capsys: pytest.CaptureFixture[str]
) -> None:
    world.db.errors["rpc.log_audit"] = failure
    target = str(uuid.uuid4())
    assert _record(world, target) is False  # never raises: the business action is already done
    out = capsys.readouterr().out
    (reported,) = reported_errors(out)
    assert reported["operation"] == "audit_write"
    assert reported["action"] == "user.invited"
    assert reported["target_id"] == target
    assert EMAIL not in out
    assert world.db.audit == []


# --- list_audit --------------------------------------------------------------------------------


def _seed(world: AdminWorld, count: int, *, same_time: str | None = None) -> list[int]:
    ids = []
    for number in range(count):
        row = world.db.add_audit(
            action="user.invited",
            target_id=f"t{number}",
            actor_id=world.admin.id if number % 2 == 0 else None,
            metadata={"email": f"u{number}@example.test"},
            created_at=same_time,
        )
        ids.append(row["id"])
    return ids


def test_list_audit_returns_the_limit_and_a_cursor_only_when_more_rows_exist(
    world: AdminWorld,
) -> None:
    ids = _seed(world, 3)
    page = list_audit(world.db, page=Page(limit=2, after=None))  # type: ignore[arg-type]
    assert isinstance(page, AuditLogPage)
    assert [entry.id for entry in page.items] == [ids[2], ids[1]]  # newest first
    assert page.next_cursor is not None
    last = page.items[-1]
    assert decode_cursor(page.next_cursor) == Cursor(
        created_at=last.created_at.isoformat(), id=str(last.id)
    )
    sent = world.db.calls_named("audit_log.select")[-1][1]
    assert sent["limit"] == 3  # limit + 1 rows are fetched to know whether there is a next page


def test_exactly_the_limit_of_rows_has_no_next_cursor(world: AdminWorld) -> None:
    _seed(world, 2)
    page = list_audit(world.db, page=Page(limit=2, after=None))  # type: ignore[arg-type]
    assert len(page.items) == 2
    assert page.next_cursor is None


def test_an_empty_log_is_an_empty_page(world: AdminWorld) -> None:
    page = list_audit(world.db, page=Page(limit=50, after=None))  # type: ignore[arg-type]
    assert (page.items, page.next_cursor) == ([], None)


def test_following_the_cursor_gives_the_rest_without_gap_or_duplicate_even_on_equal_dates(
    world: AdminWorld,
) -> None:
    ids = _seed(world, 5, same_time="2026-10-03T12:00:00.000001+00:00")
    seen: list[int] = []
    after: Cursor | None = None
    for _ in range(5):
        page = list_audit(world.db, page=Page(limit=2, after=after))  # type: ignore[arg-type]
        seen.extend(entry.id for entry in page.items)
        if page.next_cursor is None:
            break
        after = decode_cursor(page.next_cursor)
    assert seen == sorted(ids, reverse=True)


def test_the_actor_is_embedded_or_null(world: AdminWorld) -> None:
    _seed(world, 2)
    items = list_audit(world.db, page=Page(limit=10, after=None)).items  # type: ignore[arg-type]
    by_target = {entry.target_id: entry for entry in items}
    assert by_target["t0"].actor is not None
    assert (by_target["t0"].actor.id, by_target["t0"].actor.full_name) == (
        uuid.UUID(world.admin.id),
        "Boss Admin",
    )
    assert by_target["t1"].actor is None


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("down"),
        APIError({"message": "boom", "code": "XX000", "details": "", "hint": ""}),
    ],
    ids=["connect", "database"],
)
def test_a_backend_failure_is_a_503_and_is_reported_once(
    world: AdminWorld, failure: Exception, capsys: pytest.CaptureFixture[str]
) -> None:
    world.db.errors["audit_log.select"] = failure
    with pytest.raises(AppError) as error:
        list_audit(world.db, page=Page(limit=10, after=None))  # type: ignore[arg-type]
    assert (error.value.code, error.value.status) == (ErrorCode.SERVICE_UNAVAILABLE, 503)
    assert error.value.message == UNAVAILABLE
    assert len(reported_errors(capsys.readouterr().out)) == 1

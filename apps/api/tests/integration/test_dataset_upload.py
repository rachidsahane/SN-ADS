"""POST /api/v1/admin/dataset/upload: validation, insertion by batches, audit entry, errors.

Same style as the model routes: the real app and routes, the caller replaced by a known user and the
repositories (the database) replaced by a small in-memory double.
"""

import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api.deps import get_current_user, get_user_db
from app.config import Settings
from app.domain.holdout import is_holdout
from app.main import create_app
from app.repositories import dataset_repo
from app.schemas.user import CurrentUser

pytestmark = pytest.mark.integration

ADMIN = CurrentUser(id=uuid.uuid4(), role="admin", access_token="admin-token")  # noqa: S106
MARKETER = CurrentUser(id=uuid.uuid4(), role="marketer", access_token="marketer-token")  # noqa: S106
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
URL = "/api/v1/admin/dataset/upload"
VALID = (FIXTURES / "small_dataset.csv").read_bytes()
INVALID = (FIXTURES / "small_dataset_invalid.csv").read_bytes()


class FakeTable:
    """The `dataset_rows` rows of the source 'agency', and what was written."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.rows: list[dict[str, Any]] = []
        self.batches: list[int] = []
        self.audit: list[dict[str, Any]] = []
        self.fail_with: APIError | None = None
        monkeypatch.setattr(
            dataset_repo,
            "agency_external_ids",
            lambda _db: {int(row["external_id"]) for row in self.rows},
        )
        monkeypatch.setattr(dataset_repo, "add_rows", self._add)
        monkeypatch.setattr(dataset_repo, "count_rows", lambda _db, **_kw: len(self.rows))
        monkeypatch.setattr(
            "app.repositories.audit_repo.log_action", lambda _db, **kw: self.audit.append(kw)
        )

    def _add(self, _db: Any, rows: Any) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.batches.append(len(rows))
        self.rows.extend(rows)


@pytest.fixture
def table(monkeypatch: pytest.MonkeyPatch) -> FakeTable:
    return FakeTable(monkeypatch)


Make = Callable[[CurrentUser], TestClient]


@pytest.fixture
def make_client(settings: Settings) -> Iterator[Make]:
    def make(user: CurrentUser) -> TestClient:
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_user_db] = lambda: object()
        return TestClient(app)

    yield make


def upload(
    client: TestClient,
    content: bytes = VALID,
    *,
    name: str = "agency.csv",
    content_type: str = "text/csv",
) -> Any:
    return client.post(URL, files={"file": (name, content, content_type)})


def error_of(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"]
    return error


def test_a_valid_file_is_imported_as_agency_rows_by_batches(
    make_client: Make, table: FakeTable
) -> None:
    response = upload(make_client(ADMIN), name="C:\\Users\\me\\q3 campaigns.csv")
    assert response.status_code == 201, response.text
    assert response.json() == {"rows_imported": 400, "agency_rows_total": 400}
    assert table.batches == [400]
    assert {row["source"] for row in table.rows} == {"agency"}
    assert all(row["is_holdout"] == is_holdout("agency", row["external_id"]) for row in table.rows)
    assert 0 < sum(row["is_holdout"] for row in table.rows) < 400
    (entry,) = table.audit
    assert entry["action"] == "upload.accepted"
    assert entry["target_type"] == "upload"
    assert entry["metadata"] == {"file_name": "q3 campaigns.csv", "row_count": 400}


def test_a_big_file_is_written_by_batches_of_1000(
    make_client: Make, table: FakeTable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.dataset_service.BATCH_SIZE", 150)
    assert upload(make_client(ADMIN)).status_code == 201
    assert table.batches == [150, 150, 100]


def test_an_invalid_file_is_a_422_with_the_issues_and_imports_nothing(
    make_client: Make, table: FakeTable
) -> None:
    error = error_of(upload(make_client(ADMIN), INVALID), 422, "CSV_INVALID")
    assert error["message"] == "The file contains 2 errors."
    assert [(d["row"], d["column"]) for d in error["details"]] == [
        (3, "ClickThroughRate"),
        (5, "AdvertisingPlatform"),
    ]
    assert error["details"][0]["message"] == "Must be a fraction between 0 and 1 (got 5)."
    assert table.rows == [] and table.audit == []


def test_at_most_100_issues_are_listed_and_the_message_gives_the_total(
    make_client: Make, table: FakeTable
) -> None:
    lines = VALID.decode().splitlines()
    broken = [lines[0]] + [line.replace(",Male,", ",Robot,").replace(",Female,", ",Robot,")
                           for line in lines[1:]]  # fmt: skip
    error = error_of(upload(make_client(ADMIN), "\n".join(broken).encode()), 422, "CSV_INVALID")
    assert error["message"] == "The file contains 400 errors. The first 100 are listed."
    assert len(error["details"]) == 100


def test_the_same_file_twice_is_a_409_already_imported(make_client: Make, table: FakeTable) -> None:
    client = make_client(ADMIN)
    assert upload(client).status_code == 201
    error = error_of(upload(client), 409, "DUPLICATE_UPLOAD")
    assert error["message"] == "This file has already been imported."
    assert len(table.rows) == 400


def test_a_file_that_only_partly_overlaps_lists_the_ids_already_there(
    make_client: Make, table: FakeTable
) -> None:
    client = make_client(ADMIN)
    assert upload(client, b"\n".join(VALID.splitlines()[:11]) + b"\n").status_code == 201
    error = error_of(upload(client), 422, "CSV_INVALID")
    assert error["details"][0]["message"] == "Campaign number 1 was already imported."
    assert len(table.rows) == 10


def test_a_marketer_cannot_import(make_client: Make, table: FakeTable) -> None:
    error_of(upload(make_client(MARKETER)), 403, "FORBIDDEN")
    assert table.rows == []


def test_only_csv_files_are_accepted(make_client: Make, table: FakeTable) -> None:
    client = make_client(ADMIN)
    error_of(upload(client, name="data.xlsx"), 415, "UNSUPPORTED_MEDIA_TYPE")
    error_of(upload(client, content_type="application/pdf"), 415, "UNSUPPORTED_MEDIA_TYPE")
    assert upload(client, content_type="application/vnd.ms-excel").status_code == 201


def test_the_file_field_is_required(make_client: Make, table: FakeTable) -> None:
    response = make_client(ADMIN).post(URL, files={"other": ("a.csv", VALID, "text/csv")})
    error = error_of(response, 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "file"


def test_a_file_over_the_limit_is_a_413(settings: Settings, table: FakeTable) -> None:
    app = create_app(settings.model_copy(update={"max_upload_bytes": 1000}))
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_user_db] = lambda: object()
    error_of(upload(TestClient(app), VALID), 413, "PAYLOAD_TOO_LARGE")
    assert table.rows == []


def test_a_concurrent_import_of_the_same_ids_is_a_409(make_client: Make, table: FakeTable) -> None:
    table.fail_with = APIError({"message": "duplicate", "code": "23505", "details": "", "hint": ""})
    error_of(upload(make_client(ADMIN)), 409, "DUPLICATE_EXTERNAL_ID")


def test_a_database_failure_is_a_503_without_detail(make_client: Make, table: FakeTable) -> None:
    table.fail_with = APIError(
        {"message": "boom secret", "code": "XX000", "details": "", "hint": ""}
    )
    error = error_of(upload(make_client(ADMIN)), 503, "SERVICE_UNAVAILABLE")
    assert "secret" not in error["message"]
    assert table.audit == []


def test_the_summary_counts_the_agency_rows(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    def count(_db: Any, *, source: str | None = None, holdout: bool | None = None) -> int:
        return {("seed", None): 8000, ("agency", None): 400, (None, True): 1683}[(source, holdout)]

    monkeypatch.setattr(dataset_repo, "count_rows", count)
    monkeypatch.setattr(dataset_repo, "first_loaded_at", lambda _db, *, source: None)
    body = make_client(ADMIN).get("/api/v1/admin/dataset/summary").json()
    assert body["agency_rows"] == 400
    assert body["agency_loaded_at"] is None

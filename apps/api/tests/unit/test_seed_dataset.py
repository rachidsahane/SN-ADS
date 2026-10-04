"""cli/seed_dataset.py: CSV to rows, batches, idempotence."""

import io
from pathlib import Path
from typing import Any

import pytest

from app.cli import seed_dataset
from app.config import Settings
from app.domain.holdout import is_holdout

HEADER = (
    "CustomerID,Age,Gender,Income,CampaignChannel,CampaignType,AdSpend,ClickThroughRate,"
    "ConversionRate,WebsiteVisits,PagesPerVisit,TimeOnSite,SocialShares,EmailOpens,EmailClicks,"
    "PreviousPurchases,LoyaltyPoints,AdvertisingPlatform,AdvertisingTool,Conversion\n"
)


def _csv(tmp_path: Path, count: int) -> Path:
    path = tmp_path / "seed.csv"
    lines = [
        f"{8000 + i},30,Female,1000,Email,Awareness,100.5,0.1,0.2,10,2.5,3.5,1,2,3,4,5,P,T,1"
        for i in range(count)
    ]
    path.write_text(HEADER + "\n".join(lines) + "\n")
    return path


def test_the_csv_becomes_database_rows(tmp_path: Path) -> None:
    rows = seed_dataset.read_seed_csv(_csv(tmp_path, 3))
    assert len(rows) == 3
    first = rows[0]
    assert first["source"] == "seed" and first["external_id"] == 8000
    assert first["is_holdout"] == is_holdout("seed", 8000)
    assert first["campaign_channel"] == "Email" and first["conversion"] == 1
    assert isinstance(first["age"], int)


class FakeTable:
    """Stands for `dataset_rows` behind the repository functions."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.ids: set[int] = set()
        self.batches = 0
        repo = seed_dataset.dataset_repo
        monkeypatch.setattr(repo, "count_rows", lambda _db, **_k: len(self.ids))
        monkeypatch.setattr(repo, "insert_rows", self.insert)

    def insert(self, _db: Any, rows: list[dict[str, Any]]) -> None:
        self.batches += 1
        self.ids.update(int(r["external_id"]) for r in rows)


def test_rows_are_inserted_by_batches_and_a_second_run_adds_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = FakeTable(monkeypatch)
    rows = seed_dataset.read_seed_csv(_csv(tmp_path, 2500))
    assert seed_dataset.seed(None, rows) == 2500  # type: ignore[arg-type]
    assert table.batches == 3
    assert seed_dataset.seed(None, rows) == 0  # type: ignore[arg-type]


def test_main_reports_one_plain_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings: Settings
) -> None:
    FakeTable(monkeypatch)
    path = _csv(tmp_path, 10)
    monkeypatch.setattr(
        seed_dataset,
        "get_settings",
        lambda: settings.model_copy(update={"seed_csv_path": str(path)}),
    )
    out = io.StringIO()
    assert seed_dataset.main(client=object(), out=out) == 0  # type: ignore[arg-type]
    assert out.getvalue() == "Seed dataset: 10 rows added, 0 already present.\n"
    monkeypatch.setattr(seed_dataset, "get_settings", lambda: settings)
    out = io.StringIO()
    assert seed_dataset.main(client=object(), out=out) == 1  # type: ignore[arg-type]
    assert "SEED_CSV_PATH" in out.getvalue()

"""cli/demo_accounts.py and cli/train_demo.py: idempotence and secrets handling."""

import io
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.cli import demo_accounts, train_demo
from app.config import Settings
from tests.support import FakeServiceClient


def _settings(path: Path | str) -> Settings:
    return Settings(_env_file=None, demo_accounts_path=str(path))  # type: ignore[call-arg]


def test_passwords_are_written_once_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "accounts.txt"
    first = {email: f"pw-{i}" for i, (_, email, _) in enumerate(demo_accounts.ACCOUNTS)}
    demo_accounts.write_passwords(path, first)
    assert demo_accounts.read_passwords(path) == first
    assert demo_accounts.read_passwords(tmp_path / "missing.txt") == {}


def test_accounts_are_created_then_reset_with_the_same_passwords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "accounts.txt"
    monkeypatch.setattr(demo_accounts, "get_settings", lambda: _settings(path))
    service = FakeServiceClient()
    out = io.StringIO()
    assert demo_accounts.main(client=service, out=out) == 0  # type: ignore[arg-type]
    passwords = demo_accounts.read_passwords(path)
    assert len(passwords) == 2 and all(len(p) >= 12 for p in passwords.values())
    assert out.getvalue().splitlines() == ["admin: created", "marketer: created"]
    assert not any(p in out.getvalue() for p in passwords.values())  # never printed

    again = io.StringIO()
    assert demo_accounts.main(client=service, out=again) == 0  # type: ignore[arg-type]
    assert again.getvalue().splitlines() == ["admin: reset", "marketer: reset"]
    assert demo_accounts.read_passwords(path) == passwords


def test_demo_accounts_need_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_accounts, "get_settings", lambda: _settings(""))
    out = io.StringIO()
    assert demo_accounts.main(client=object(), out=out) == 1  # type: ignore[arg-type]
    assert "DEMO_ACCOUNTS_PATH" in out.getvalue()


class FakeVersions:
    """The repository functions of `train_demo` over a tiny in-memory state."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, active: bool, succeeded: bool) -> None:
        self.active = uuid.uuid4() if active else None
        self.succeeded = uuid.uuid4() if succeeded else None
        self.trained = 0
        repo = train_demo.versions
        monkeypatch.setattr(repo, "active_id", lambda _db: self.active and str(self.active))
        monkeypatch.setattr(repo, "latest_succeeded_id", lambda _db: self.succeeded)
        monkeypatch.setattr(repo, "insert_system_queued", lambda _db: uuid.uuid4())
        monkeypatch.setattr(repo, "set_active", self.set_active)
        monkeypatch.setattr(train_demo, "run_training_job", self.train)

    def set_active(self, _db: Any, version_id: uuid.UUID) -> None:
        self.active = version_id

    def train(self, version_id: uuid.UUID, **_kwargs: Any) -> None:
        self.trained += 1
        self.succeeded = version_id


def test_train_demo_does_nothing_when_a_version_is_active(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeVersions(monkeypatch, active=True, succeeded=True)
    assert train_demo.ensure_active_version(object(), tmp_path) == "already active"  # type: ignore[arg-type]
    assert world.trained == 0


def test_train_demo_activates_an_existing_version_without_training(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeVersions(monkeypatch, active=False, succeeded=True)
    assert train_demo.ensure_active_version(object(), tmp_path) == "activated"  # type: ignore[arg-type]
    assert world.active == world.succeeded and world.trained == 0


def test_train_demo_trains_then_activates_and_reports_a_failed_training(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeVersions(monkeypatch, active=False, succeeded=False)
    assert train_demo.ensure_active_version(object(), tmp_path) == "trained and activated"  # type: ignore[arg-type]
    assert world.trained == 1 and world.active == world.succeeded

    broken = FakeVersions(monkeypatch, active=False, succeeded=False)
    monkeypatch.setattr(train_demo, "run_training_job", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="did not succeed"):
        train_demo.ensure_active_version(object(), tmp_path)  # type: ignore[arg-type]
    assert broken.active is None

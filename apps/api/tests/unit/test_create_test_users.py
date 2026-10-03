"""cli/create_test_users.py: the local Playwright accounts (SEC-18: never in production).

A fake service-role client records every call. Passwords are generated here at run time.
"""

import io
import secrets
from collections.abc import Callable, Iterator

import pytest

from app.cli.create_test_users import main
from app.config import get_settings
from tests.support import WEB_APP_URL, FakeServiceClient

ACCOUNTS = {
    "ADMIN": ("e2e-admin@example.test", "admin", "E2E Admin"),
    "ADMIN2": ("e2e-admin2@example.test", "admin", "E2E Admin Two"),
    "MARKETER_A": ("e2e-marketer-a@example.test", "marketer", "E2E Marketer A"),
    "MARKETER_B": ("e2e-marketer-b@example.test", "marketer", "E2E Marketer B"),
    "RESET": ("e2e-reset@example.test", "marketer", "E2E Reset User"),
}
INVITEE = "e2e-invitee@example.test"


def _passwords() -> dict[str, str]:
    return {name: "Pw-" + secrets.token_hex(10) for name in ACCOUNTS}


def _configure(
    monkeypatch: pytest.MonkeyPatch, passwords: dict[str, str], app_env: str = "local"
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    for name, (email, _role, _full_name) in ACCOUNTS.items():
        monkeypatch.setenv(f"E2E_{name}_EMAIL", email)
        monkeypatch.setenv(f"E2E_{name}_PASSWORD", passwords[name])
    monkeypatch.setenv("E2E_INVITEE_EMAIL", INVITEE)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def cli_environment(
    monkeypatch: pytest.MonkeyPatch, make_jwt: Callable[[str], str]
) -> Iterator[None]:
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", make_jwt("anon"))
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", make_jwt("service_role"))
    monkeypatch.setenv("WEB_APP_URL", WEB_APP_URL)
    for name in ("FIRST_ADMIN_EMAIL", "FIRST_ADMIN_FULL_NAME"):
        monkeypatch.delenv(name, raising=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def passwords(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    values = _passwords()
    _configure(monkeypatch, values)
    return values


@pytest.fixture
def fake() -> FakeServiceClient:
    return FakeServiceClient()


def _run(fake: FakeServiceClient) -> tuple[int, str]:
    out = io.StringIO()
    code = main([], client=fake, out=out)  # type: ignore[arg-type]
    return code, out.getvalue()


# --- production guard (SEC-18) ----------------------------------------------------------------


def test_it_refuses_to_run_in_production_before_any_call(
    monkeypatch: pytest.MonkeyPatch, fake: FakeServiceClient
) -> None:
    _configure(monkeypatch, _passwords(), app_env="production")
    code, out = _run(fake)
    assert code == 1
    assert "refused in production" in out
    assert fake.calls == []
    assert fake.users == {}


def test_the_production_guard_needs_no_other_configuration(
    monkeypatch: pytest.MonkeyPatch, fake: FakeServiceClient
) -> None:
    """Even with no test variable at all, production is refused with the production message."""
    for name in (f"E2E_{n}_{k}" for n in ACCOUNTS for k in ("EMAIL", "PASSWORD")):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    code, out = _run(fake)
    assert code == 1
    assert "refused in production" in out


# --- creation ---------------------------------------------------------------------------------


def test_the_five_accounts_are_created_confirmed_with_their_role_and_name(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    code, _ = _run(fake)
    assert code == 0
    for name, (email, role, full_name) in ACCOUNTS.items():
        user = fake.user_by_email(email)
        assert user is not None, email
        assert user.confirmed is True
        assert user.password == passwords[name]
        profile = fake.profile_of(email)
        assert (profile["role"], profile["full_name"], profile["is_active"]) == (
            role,
            full_name,
            True,
        )


def test_accounts_are_created_with_the_documented_attributes(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    _run(fake)
    created = {email: attrs for _, email, attrs in fake.calls_named("create_user")}
    attrs = created[ACCOUNTS["MARKETER_A"][0]]
    assert attrs["email_confirm"] is True
    assert attrs["password"] == passwords["MARKETER_A"]
    assert attrs["user_metadata"] == {"full_name": "E2E Marketer A"}


def test_administrators_are_created_before_the_marketers(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    _run(fake)
    order = [email for _, email, _attrs in fake.calls_named("create_user")]
    admins = [ACCOUNTS["ADMIN"][0], ACCOUNTS["ADMIN2"][0]]
    marketers = [ACCOUNTS[n][0] for n in ("MARKETER_A", "MARKETER_B", "RESET")]
    assert max(order.index(email) for email in admins) < min(order.index(m) for m in marketers)


def test_the_invitee_is_invited_once_with_the_redirect_to_the_confirm_route(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    _run(fake)
    ((_, email, options),) = fake.calls_named("invite")
    assert email == INVITEE
    assert options["data"] == {"full_name": "E2E Invitee"}
    assert options["redirect_to"] == f"{WEB_APP_URL}/auth/confirm"
    assert fake.user_by_email(INVITEE).confirmed is False  # type: ignore[union-attr]
    assert fake.profile_of(INVITEE)["role"] == "marketer"


# --- idempotence ------------------------------------------------------------------------------


def test_a_second_run_resets_the_passwords_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch, fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    assert _run(fake)[0] == 0
    users_before = dict(fake.users)
    renewed = _passwords()
    _configure(monkeypatch, renewed)
    code, _ = _run(fake)
    assert code == 0
    assert set(fake.users) == set(users_before)  # nobody was duplicated
    for name, (email, _role, _full_name) in ACCOUNTS.items():
        assert fake.user_by_email(email).password == renewed[name]  # type: ignore[union-attr]
    assert len(fake.calls_named("create_user")) == len(ACCOUNTS)  # created only the first time
    assert len(fake.calls_named("update_user")) >= len(ACCOUNTS)


def test_a_second_run_repairs_drifted_accounts(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    fake.seed(ACCOUNTS["MARKETER_A"][0], role="marketer", confirmed=False, is_active=False)
    fake.seed(ACCOUNTS["ADMIN"][0], role="marketer", confirmed=True)
    assert _run(fake)[0] == 0
    marketer = fake.profile_of(ACCOUNTS["MARKETER_A"][0])
    assert marketer["is_active"] is True
    assert fake.user_by_email(ACCOUNTS["MARKETER_A"][0]).confirmed is True  # type: ignore[union-attr]
    assert fake.profile_of(ACCOUNTS["ADMIN"][0])["role"] == "admin"


def test_demotions_never_run_before_the_administrators_exist(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    """The database refuses to demote the last administrator: order matters (guard_last_admin)."""
    fake.seed(ACCOUNTS["MARKETER_A"][0], role="admin", confirmed=True)  # the only admin so far
    code, _ = _run(fake)
    assert code == 0
    assert fake.profile_of(ACCOUNTS["MARKETER_A"][0])["role"] == "marketer"
    assert fake.profile_of(ACCOUNTS["ADMIN"][0])["role"] == "admin"


def test_a_confirmed_invitee_is_left_alone(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    fake.seed(INVITEE, role="marketer", confirmed=True, full_name="Someone")
    _run(fake)
    assert fake.calls_named("invite") == []
    assert fake.profile_of(INVITEE)["full_name"] == "Someone"


def test_a_pending_invitee_is_invited_again(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    fake.seed(INVITEE, role="marketer", confirmed=False)
    _run(fake)
    assert len(fake.calls_named("invite")) == 1
    assert len([u for u in fake.users.values() if u.email == INVITEE]) == 1


# --- nothing secret is shown ------------------------------------------------------------------


def test_passwords_are_never_printed_or_logged(
    fake: FakeServiceClient,
    passwords: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(fake)
    captured = capsys.readouterr()
    for value in passwords.values():
        assert value not in out
        assert value not in captured.out
        assert value not in captured.err


def test_the_output_names_accounts_not_values(
    fake: FakeServiceClient, passwords: dict[str, str]
) -> None:
    _, out = _run(fake)
    assert out.strip()
    assert "Traceback" not in out


def test_missing_configuration_is_one_plain_message_naming_the_variables(
    monkeypatch: pytest.MonkeyPatch, fake: FakeServiceClient, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    for account in ACCOUNTS:
        monkeypatch.delenv(f"E2E_{account}_PASSWORD", raising=False)
    get_settings.cache_clear()
    code, out = _run(fake)
    captured = capsys.readouterr()
    assert code != 0
    assert "E2E_ADMIN_PASSWORD" in out + captured.err + captured.out
    assert "Traceback" not in out + captured.err + captured.out
    assert fake.calls == []

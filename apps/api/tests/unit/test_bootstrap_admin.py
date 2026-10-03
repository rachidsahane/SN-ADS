"""cli/bootstrap_admin.py: create or re-invite the first administrator, idempotently.

A fake service-role client records every call (gotrue admin API + the profiles table). No network.
"""

import io
import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

from app.cli.bootstrap_admin import main
from app.config import Settings, get_settings
from app.infra.observability import configure_logging
from tests.support import WEB_APP_URL, FakeServiceClient

EMAIL = "first.admin@example.test"
NAME = "First Admin"
ARGV = ["--email", EMAIL, "--full-name", NAME]
REDIRECT = f"{WEB_APP_URL}/auth/confirm"


@pytest.fixture(autouse=True)
def cli_environment(
    monkeypatch: pytest.MonkeyPatch, make_jwt: Callable[[str], str]
) -> Iterator[None]:
    for name in ("FIRST_ADMIN_EMAIL", "FIRST_ADMIN_FULL_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", make_jwt("anon"))
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", make_jwt("service_role"))
    monkeypatch.setenv("WEB_APP_URL", WEB_APP_URL)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake() -> FakeServiceClient:
    return FakeServiceClient()


def _run(argv: list[str], fake: FakeServiceClient) -> tuple[int, str]:
    out = io.StringIO()
    try:
        code = main(argv, client=fake, out=out)  # type: ignore[arg-type]
    except SystemExit as exit_request:  # argparse reports bad usage this way
        code = int(exit_request.code or 0)
    return code, out.getvalue().strip()


# --- the six rows of the behaviour table ------------------------------------------------------


def test_a_new_administrator_is_invited_and_made_admin(fake: FakeServiceClient) -> None:
    code, out = _run(ARGV, fake)
    assert (code, out) == (0, f"Invitation sent to {EMAIL}. Open the mailbox to read it.")
    ((_, email, options),) = fake.calls_named("invite")
    assert email == EMAIL
    assert options["data"] == {"full_name": NAME}
    assert options["redirect_to"] == REDIRECT
    assert fake.profile_of(EMAIL)["role"] == "admin"
    assert fake.profile_of(EMAIL)["full_name"] == NAME


def test_an_unconfirmed_account_is_invited_again_and_ensured_admin(
    fake: FakeServiceClient,
) -> None:
    fake.seed(EMAIL, role="marketer", confirmed=False)
    code, out = _run(ARGV, fake)
    assert (code, out) == (0, f"Invitation sent again to {EMAIL}.")
    assert len(fake.calls_named("invite")) == 1
    assert fake.profile_of(EMAIL)["role"] == "admin"
    assert len(fake.users) == 1


def test_a_confirmed_non_admin_is_only_promoted_and_no_mail_is_sent(
    fake: FakeServiceClient,
) -> None:
    fake.seed("someone.else@example.test", role="admin")  # keeps an admin around
    fake.seed(EMAIL, role="marketer", confirmed=True)
    code, out = _run(ARGV, fake)
    assert (code, out) == (0, f"{EMAIL} is now an administrator.")
    assert fake.profile_of(EMAIL)["role"] == "admin"
    assert fake.calls_named("invite") == []
    assert fake.calls_named("generate_link") == []


def test_an_active_confirmed_admin_means_nothing_to_do(fake: FakeServiceClient) -> None:
    fake.seed(EMAIL, role="admin", confirmed=True)
    code, out = _run(ARGV, fake)
    assert (code, out) == (0, f"{EMAIL} is already an active administrator. Nothing to do.")
    assert fake.calls == []


def test_a_deactivated_account_is_refused_and_left_untouched(fake: FakeServiceClient) -> None:
    fake.seed(EMAIL, role="marketer", confirmed=True, is_active=False)
    code, out = _run(ARGV, fake)
    assert (code, out) == (1, "The account is deactivated. Reactivate it before bootstrapping.")
    assert fake.calls == []
    assert fake.profile_of(EMAIL)["role"] == "marketer"


def test_a_deactivated_unconfirmed_account_is_refused_too(fake: FakeServiceClient) -> None:
    fake.seed(EMAIL, role="marketer", confirmed=False, is_active=False)
    code, _ = _run(ARGV, fake)
    assert code == 1
    assert fake.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        AuthApiError("internal-detail", 500, "unexpected_failure"),  # type: ignore[arg-type]
        AuthApiError("internal-detail", 422, "email_address_invalid"),  # type: ignore[arg-type]
    ],
)
def test_a_gotrue_error_is_one_plain_line_without_a_traceback(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str], failure: Exception
) -> None:
    fake.errors["invite_user_by_email"] = failure
    code, out = _run(ARGV, fake)
    captured = capsys.readouterr()
    assert code == 1
    assert (out + captured.err).strip(), "the operator must be told what went wrong"
    assert "Traceback" not in out + captured.out + captured.err
    assert "internal-detail" not in out + captured.err


def test_a_network_error_is_one_plain_line_without_a_traceback(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.errors["invite_user_by_email"] = httpx.ConnectError("refused")
    code, out = _run(ARGV, fake)
    captured = capsys.readouterr()
    assert code == 1
    assert (out + captured.err).strip()
    assert "Traceback" not in out + captured.out + captured.err


def test_a_failing_profile_update_is_reported_without_a_traceback(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.seed(EMAIL, role="marketer", confirmed=True)

    # The profile table refuses (last admin guard can never fire here, so force a database error).
    def boom(*_: object, **__: object) -> None:
        raise APIError({"message": "boom", "code": "XX000", "details": "", "hint": ""})

    fake.apply_profile_update = boom  # type: ignore[method-assign]
    code, out = _run(ARGV, fake)
    captured = capsys.readouterr()
    assert code == 1
    assert "Traceback" not in out + captured.out + captured.err


# --- inputs -----------------------------------------------------------------------------------


def test_the_email_is_lower_cased(fake: FakeServiceClient) -> None:
    code, _ = _run(["--email", "First.Admin@Example.TEST", "--full-name", NAME], fake)
    assert code == 0
    ((_, email, _options),) = fake.calls_named("invite")
    assert email == EMAIL


def test_the_full_name_is_stripped(fake: FakeServiceClient) -> None:
    code, _ = _run(["--email", EMAIL, "--full-name", "  First Admin  "], fake)
    assert code == 0
    ((_, _email, options),) = fake.calls_named("invite")
    assert options["data"] == {"full_name": NAME}


@pytest.mark.parametrize(
    "argv",
    [
        ["--email", "not-an-email", "--full-name", NAME],
        ["--email", "a b@example.test", "--full-name", NAME],
        ["--email", "x" * 250 + "@example.test", "--full-name", NAME],
        ["--email", "", "--full-name", NAME],
        ["--email", EMAIL, "--full-name", ""],
        ["--email", EMAIL, "--full-name", "   "],
        ["--email", EMAIL, "--full-name", "N" * 121],
        ["--email", EMAIL, "--full-name", "Bad\x00Name"],
        ["--email", EMAIL, "--full-name", "Line\nBreak"],
        [],
    ],
)
def test_invalid_or_missing_input_exits_2_before_any_call(
    fake: FakeServiceClient, argv: list[str]
) -> None:
    code, _ = _run(argv, fake)
    assert code == 2
    assert fake.calls == []
    assert fake.users == {}


def test_a_name_of_120_characters_is_accepted(fake: FakeServiceClient) -> None:
    code, _ = _run(["--email", EMAIL, "--full-name", "N" * 120], fake)
    assert code == 0


def test_the_defaults_come_from_first_admin_variables(
    fake: FakeServiceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIRST_ADMIN_EMAIL", EMAIL)
    monkeypatch.setenv("FIRST_ADMIN_FULL_NAME", NAME)
    get_settings.cache_clear()
    code, out = _run([], fake)
    assert (code, out) == (0, f"Invitation sent to {EMAIL}. Open the mailbox to read it.")


def test_the_arguments_win_over_the_variables(
    fake: FakeServiceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIRST_ADMIN_EMAIL", "from.env@example.test")
    monkeypatch.setenv("FIRST_ADMIN_FULL_NAME", "From Env")
    get_settings.cache_clear()
    _run(ARGV, fake)
    assert fake.user_by_email(EMAIL) is not None
    assert fake.user_by_email("from.env@example.test") is None


# --- idempotence ------------------------------------------------------------------------------


def test_running_it_again_and_again_never_duplicates_or_fails(fake: FakeServiceClient) -> None:
    first = _run(ARGV, fake)
    second = _run(ARGV, fake)
    assert first[0] == 0
    assert second == (0, f"Invitation sent again to {EMAIL}.")
    assert len(fake.users) == 1
    fake.user_by_email(EMAIL).confirmed = True  # type: ignore[union-attr]
    calls_before = len(fake.calls)
    third = _run(ARGV, fake)
    assert third == (0, f"{EMAIL} is already an active administrator. Nothing to do.")
    assert len(fake.calls) == calls_before
    assert len(fake.users) == 1


# --- --print-link -----------------------------------------------------------------------------


def test_print_link_prints_the_web_link_and_sends_no_email(fake: FakeServiceClient) -> None:
    code, out = _run([*ARGV, "--print-link"], fake)
    assert code == 0
    expected = (
        f"{WEB_APP_URL}/auth/confirm?token_hash={fake.last_hashed_token}"
        "&type=invite&next=/auth/set-password"
    )
    assert fake.last_hashed_token
    assert expected in out
    assert "single-use" in out
    assert "do not share" in out
    assert fake.calls_named("invite") == []
    assert len(fake.calls_named("generate_link")) == 1
    ((_, params),) = fake.calls_named("generate_link")
    assert params["type"] == "invite"
    assert params["email"] == EMAIL
    assert fake.profile_of(EMAIL)["role"] == "admin"


def test_print_link_never_prints_the_gotrue_action_link(fake: FakeServiceClient) -> None:
    _, out = _run([*ARGV, "--print-link"], fake)
    assert "/auth/v1/verify" not in out
    assert "supabase.test" not in out


def test_the_link_goes_to_the_output_only_never_to_the_logs(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str], settings: Settings
) -> None:
    configure_logging(settings)
    _run([*ARGV, "--print-link"], fake)
    captured = capsys.readouterr()
    assert fake.last_hashed_token not in captured.out + captured.err


def test_the_hashed_token_is_not_logged_in_the_normal_mode_either(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str], settings: Settings
) -> None:
    configure_logging(settings)
    _run(ARGV, fake)
    seen = capsys.readouterr()
    assert fake.last_hashed_token not in seen.out + seen.err
    assert "hashed_token" not in seen.out + seen.err


# --- secrets ----------------------------------------------------------------------------------


def test_an_empty_service_key_is_refused_with_exit_1_and_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    get_settings.cache_clear()
    out = io.StringIO()
    code = main(ARGV, out=out)
    captured = capsys.readouterr()
    seen = out.getvalue() + captured.out + captured.err
    assert code == 1
    assert "SUPABASE_SERVICE_ROLE_KEY" in seen
    assert "Traceback" not in seen


def test_error_text_never_contains_a_key(
    fake: FakeServiceClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    make_jwt: Callable[[str], str],
) -> None:
    service = make_jwt("service_role")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", service)
    get_settings.cache_clear()
    fake.errors["invite_user_by_email"] = AuthApiError(f"bad key {service}", 401, "bad_jwt")  # type: ignore[arg-type]
    _, out = _run(ARGV, fake)
    captured = capsys.readouterr()
    assert service not in out + captured.out + captured.err


def test_the_log_lines_are_json_and_carry_no_email_value(
    fake: FakeServiceClient, capsys: pytest.CaptureFixture[str], settings: Settings
) -> None:
    configure_logging(settings)
    _run(ARGV, fake)
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("{"):
            assert EMAIL not in json.dumps(json.loads(line))

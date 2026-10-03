"""bootstrap_admin against the real local stack (needs `make up`; hosts are service names).

The e-mail goes to Mailpit; everything created here (user, profile, messages) is removed.
"""

import io
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.cli.bootstrap_admin import main
from app.config import Settings
from app.infra.supabase_clients import get_anon_client, get_service_client

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stack")]

MAILPIT = "http://mailpit:8025"
TIMEOUT = 10.0
FULL_NAME = "Phase Two Admin"


@pytest.fixture
def email() -> str:
    return f"phase2-admin-{uuid.uuid4()}@example.test"


@pytest.fixture
def mail() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=MAILPIT, timeout=TIMEOUT) as client:
        yield client


@pytest.fixture
def cleanup(stack_settings: Settings, mail: httpx.Client, email: str) -> Iterator[None]:
    yield
    service = get_service_client(stack_settings)
    rows = service.table("profiles").select("id").eq("email", email).execute().data
    for row in rows:
        service.auth.admin.delete_user(row["id"])
    listing = mail.get("/api/v1/search", params={"query": f"to:{email}"}).json()
    ids = [message["ID"] for message in listing.get("messages", [])]
    if ids:
        mail.request("DELETE", "/api/v1/messages", json={"IDs": ids})


def _profiles(stack_settings: Settings, email: str) -> list[dict[str, Any]]:
    service = get_service_client(stack_settings)
    data = (
        (service.table("profiles").select("id,email,full_name,role,is_active").eq("email", email))
        .execute()
        .data
    )
    return list(data)


def _latest_mail(mail: httpx.Client, email: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        listing = mail.get("/api/v1/search", params={"query": f"to:{email}"}).json()
        if listing.get("messages"):
            return dict(mail.get(f"/api/v1/message/{listing['messages'][0]['ID']}").json())
        time.sleep(0.5)
    pytest.fail(f"no e-mail reached Mailpit for {email} within {TIMEOUT:.0f} seconds")


def _run(email: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(["--email", email, "--full-name", FULL_NAME], out=out)
    return code, out.getvalue().strip()


@pytest.mark.usefixtures("cleanup")
def test_the_first_administrator_is_invited_and_made_admin(
    stack_settings: Settings, mail: httpx.Client, email: str
) -> None:
    code, out = _run(email)
    assert (code, out) == (0, f"Invitation sent to {email}. Open the mailbox to read it.")
    (profile,) = _profiles(stack_settings, email)
    assert (profile["role"], profile["full_name"], profile["is_active"]) == (
        "admin",
        FULL_NAME,
        True,
    )
    message = _latest_mail(mail, email)
    assert message["Subject"] == "You have been invited to Soro Nua Campaign Predictor"


@pytest.mark.usefixtures("cleanup")
def test_a_second_run_succeeds_without_a_second_user(
    stack_settings: Settings, mail: httpx.Client, email: str
) -> None:
    assert _run(email)[0] == 0
    code, out = _run(email)
    assert (code, out) == (0, f"Invitation sent again to {email}.")
    assert len(_profiles(stack_settings, email)) == 1


@pytest.mark.usefixtures("cleanup")
def test_the_emailed_token_logs_the_administrator_in(
    stack_settings: Settings, mail: httpx.Client, email: str
) -> None:
    assert _run(email)[0] == 0
    html = _latest_mail(mail, email)["HTML"].replace("&amp;", "&")
    found = re.search(r"token_hash=([0-9A-Za-z_-]+)&type=invite", html)
    assert found, "the invitation e-mail has no token_hash link"
    anon = get_anon_client(stack_settings)
    session = anon.auth.verify_otp({"token_hash": found.group(1), "type": "invite"}).session
    assert session is not None
    assert session.access_token
    # Single use (E2E-AUTH-06): the same link is refused the second time.
    with pytest.raises(Exception, match="(?i)expired|invalid"):
        get_anon_client(stack_settings).auth.verify_otp(
            {"token_hash": found.group(1), "type": "invite"}
        )


@pytest.mark.usefixtures("cleanup")
def test_print_link_creates_the_account_without_sending_any_e_mail(
    stack_settings: Settings, mail: httpx.Client, email: str
) -> None:
    out = io.StringIO()
    code = main(["--email", email, "--full-name", FULL_NAME, "--print-link"], out=out)
    assert code == 0
    assert f"{stack_settings.web_app_url}/auth/confirm?token_hash=" in out.getvalue()
    assert "type=invite&next=/auth/set-password" in out.getvalue()
    (profile,) = _profiles(stack_settings, email)
    assert profile["role"] == "admin"
    time.sleep(1.5)
    listing = mail.get("/api/v1/search", params={"query": f"to:{email}"}).json()
    assert listing.get("messages", []) == []

"""repositories/profiles_repo.py: one profile by id, read with the client it is given.

The real supabase-py client talks to an in-process PostgREST, so the test proves the columns, the
filter and the credentials that go over the wire.
"""

import uuid

from app.config import Settings
from app.infra.supabase_clients import get_user_client
from app.repositories.profiles_repo import get_profile
from app.schemas.user import Profile
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

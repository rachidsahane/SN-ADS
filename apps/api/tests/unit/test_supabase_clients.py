"""infra/supabase_clients.py: user client per request, one cached service client (ARCH 2.5)."""

from collections.abc import Callable, Iterator

import pytest
from pydantic import SecretStr
from supabase import Client
from supabase._sync.client import SupabaseException  # not re-exported by supabase 2.10

from app.config import ConfigError, Settings, get_settings
from app.infra.supabase_clients import get_anon_client, get_service_client, get_user_client

MakeJwt = Callable[[str], str]


@pytest.fixture
def jwt_settings(settings: Settings, make_jwt: MakeJwt) -> Settings:
    """The shared test settings, with keys that look like JWTs (supabase-py validates the shape)."""
    return settings.model_copy(
        update={
            "supabase_anon_key": SecretStr(make_jwt("anon")),
            "supabase_service_role_key": SecretStr(make_jwt("service_role")),
        }
    )


@pytest.fixture(autouse=True)
def fresh_service_client_cache() -> Iterator[None]:
    get_service_client.cache_clear()  # type: ignore[attr-defined]
    yield
    get_service_client.cache_clear()  # type: ignore[attr-defined]


def _headers(client: Client) -> dict[str, str]:
    """Headers really sent to PostgREST, lower-cased."""
    return {name.lower(): value for name, value in client.postgrest.session.headers.items()}


def test_anon_client_targets_the_configured_url_with_the_anon_key(jwt_settings: Settings) -> None:
    client = get_anon_client(jwt_settings)
    anon = jwt_settings.supabase_anon_key.get_secret_value()
    assert client.supabase_url == jwt_settings.supabase_url
    assert _headers(client)["apikey"] == anon
    assert _headers(client)["authorization"] == f"Bearer {anon}"


def test_user_client_carries_the_user_token_and_the_public_key(
    jwt_settings: Settings, make_jwt: MakeJwt
) -> None:
    user_jwt = make_jwt("authenticated")
    client = get_user_client(user_jwt, jwt_settings)
    headers = _headers(client)
    assert client.supabase_url == jwt_settings.supabase_url
    assert headers["authorization"] == f"Bearer {user_jwt}"
    assert headers["apikey"] == jwt_settings.supabase_anon_key.get_secret_value()


def test_user_client_never_carries_the_service_key(
    jwt_settings: Settings, make_jwt: MakeJwt
) -> None:
    client = get_user_client(make_jwt("authenticated"), jwt_settings)
    service = jwt_settings.supabase_service_role_key.get_secret_value()
    assert service not in _headers(client).values()


def test_user_client_is_a_new_object_for_every_call(
    jwt_settings: Settings, make_jwt: MakeJwt
) -> None:
    user_jwt = make_jwt("authenticated")
    assert get_user_client(user_jwt, jwt_settings) is not get_user_client(user_jwt, jwt_settings)


def test_user_clients_do_not_share_tokens(jwt_settings: Settings, make_jwt: MakeJwt) -> None:
    first_jwt, second_jwt = make_jwt("authenticated"), make_jwt("authenticated") + "x"
    first = get_user_client(first_jwt, jwt_settings)
    second = get_user_client(second_jwt, jwt_settings)
    assert _headers(first)["authorization"] == f"Bearer {first_jwt}"
    assert _headers(second)["authorization"] == f"Bearer {second_jwt}"


def test_service_client_uses_the_service_key(jwt_settings: Settings) -> None:
    client = get_service_client(jwt_settings)
    service = jwt_settings.supabase_service_role_key.get_secret_value()
    assert client.supabase_url == jwt_settings.supabase_url
    assert _headers(client)["apikey"] == service
    assert _headers(client)["authorization"] == f"Bearer {service}"


def test_service_client_is_a_single_cached_instance(jwt_settings: Settings) -> None:
    assert get_service_client(jwt_settings) is get_service_client(jwt_settings)


def test_service_client_without_arguments_reads_the_application_settings(
    monkeypatch: pytest.MonkeyPatch, make_jwt: MakeJwt
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_NAME", "api")
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", make_jwt("anon"))
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", make_jwt("service_role"))
    get_settings.cache_clear()
    try:
        assert get_service_client() is get_service_client()
    finally:
        get_settings.cache_clear()


def test_anon_and_service_clients_are_different_objects(jwt_settings: Settings) -> None:
    assert get_anon_client(jwt_settings) is not get_service_client(jwt_settings)


def test_empty_anon_key_is_an_explicit_error_for_anon_and_user_clients(
    jwt_settings: Settings, make_jwt: MakeJwt
) -> None:
    empty = jwt_settings.model_copy(update={"supabase_anon_key": SecretStr("")})
    with pytest.raises(ConfigError, match="SUPABASE_ANON_KEY"):
        get_anon_client(empty)
    with pytest.raises(ConfigError, match="SUPABASE_ANON_KEY"):
        get_user_client(make_jwt("authenticated"), empty)


def test_empty_service_key_is_an_explicit_error(jwt_settings: Settings) -> None:
    empty = jwt_settings.model_copy(update={"supabase_service_role_key": SecretStr("")})
    with pytest.raises(ConfigError, match="SUPABASE_SERVICE_ROLE_KEY"):
        get_service_client(empty)


def test_empty_user_token_is_refused_instead_of_falling_back_to_the_anon_key(
    jwt_settings: Settings,
) -> None:
    with pytest.raises(ValueError, match="access token"):
        get_user_client("", jwt_settings)


def test_a_malformed_key_is_refused_without_echoing_its_value(settings: Settings) -> None:
    bad_value = "not-a-jwt-test-only-value"
    broken = settings.model_copy(update={"supabase_anon_key": SecretStr(bad_value)})
    with pytest.raises((ConfigError, SupabaseException)) as error:
        get_anon_client(broken)
    assert bad_value not in str(error.value)

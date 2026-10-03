"""The only place that builds Supabase clients (ARCHITECTURE 2.5, CLAUDE 4.2).

- `get_user_client`: one new client per request, with the caller's own token (RLS applies).
- `get_anon_client`: public key, no user.
- `get_service_client`: the service-role key, one cached instance. It is defined here and only here;
  `tests/unit/test_architecture.py` limits its importers to the closed list of ARCHITECTURE 2.5.
"""

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import ConfigError, Settings, get_settings


def _client(settings: Settings, key: str, authorization: str | None = None) -> Client:
    """Build a client that never stores a session or starts a refresh timer."""
    # `Connection: close`: clients are built per request and dropped, so a kept-alive socket would
    # only wait for the garbage collector (ResourceWarning) instead of closing with the response.
    headers = {"Connection": "close"}
    if authorization:
        headers["Authorization"] = f"Bearer {authorization}"
    options = ClientOptions(auto_refresh_token=False, persist_session=False)
    options.headers.update(headers)
    return create_client(settings.supabase_url, key, options)


def _required(value: str, variable: str) -> str:
    if not value:
        raise ConfigError(f"{variable} is empty. Run 'make env-local' to generate the local keys.")
    return value


def get_anon_client(settings: Settings | None = None) -> Client:
    """Client with the public (anon) key and no user token."""
    settings = settings or get_settings()
    anon = _required(settings.supabase_anon_key.get_secret_value(), "SUPABASE_ANON_KEY")
    return _client(settings, anon)


def get_user_client(access_token: str, settings: Settings | None = None) -> Client:
    """New client for one request: public key as `apikey`, the user's token as `Authorization`."""
    if not access_token:
        raise ValueError("An access token is required to build a user client.")
    settings = settings or get_settings()
    anon = _required(settings.supabase_anon_key.get_secret_value(), "SUPABASE_ANON_KEY")
    return _client(settings, anon, access_token)


@lru_cache(maxsize=1)
def get_service_client(settings: Settings | None = None) -> Client:
    """The single service-role client (bypasses RLS). Closed list of callers: ARCHITECTURE 2.5."""
    settings = settings or get_settings()
    service = _required(
        settings.supabase_service_role_key.get_secret_value(), "SUPABASE_SERVICE_ROLE_KEY"
    )
    return _client(settings, service)

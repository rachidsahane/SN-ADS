"""Test doubles shared by the phase 2 tests (no network, no new dependency).

- `FakeRedis`: a dict with TTLs that can be told to fail like a Redis outage.
- `ProfileServer`: a tiny in-process PostgREST that answers `GET /rest/v1/profiles`. The real
  supabase-py client talks to it, so tests stay independent from how the code under test builds
  its calls (and prove which token and key are sent).
- `FakeServiceClient`: the part of the service-role Supabase client used by the CLI commands
  (gotrue admin API + the `profiles` table), with the database trigger rules that matter.

Every secret-looking value is assembled at run time, never written as a literal, so that scanners
and the S105/S106 lint rules have nothing to flag.
"""

import json
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

JWT_SECRET = "test-only-" + "k" * 40
OTHER_JWT_SECRET = "other-test-" + "z" * 40
JWT_ISSUER = "http://supabase.test/auth/v1"
WEB_APP_URL = "http://localhost:3000"
UNREACHABLE_URL = "http://127.0.0.1:9"  # discard port: connection refused at once
UNREACHABLE_REDIS = "redis://127.0.0.1:9/0"


def random_value(prefix: str = "v") -> str:
    return f"{prefix}-{secrets.token_hex(12)}"


# --- Redis -------------------------------------------------------------------------------------


class FakeRedis:
    """Enough of redis.Redis for the profile cache. `error` makes every call raise it."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.calls: list[str] = []

    def _enter(self, name: str) -> None:
        self.calls.append(name)
        if self.error is not None:
            raise self.error

    def get(self, key: str) -> str | None:
        self._enter("get")
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int | None = None, **_: Any) -> bool:
        self._enter("set")
        self.data[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def setex(self, key: str, time: int, value: str) -> bool:
        self._enter("setex")
        self.data[key] = value
        self.ttls[key] = time
        return True

    def delete(self, *keys: str) -> int:
        self._enter("delete")
        removed = 0
        for key in keys:
            if self.data.pop(key, None) is not None:
                removed += 1
            self.ttls.pop(key, None)
        return removed

    def ttl(self, key: str) -> int:
        self._enter("ttl")
        if key not in self.data:
            return -2
        return self.ttls.get(key, -1)

    def ping(self) -> bool:
        self._enter("ping")
        return True

    def close(self) -> None:
        self.calls.append("close")


# --- PostgREST ---------------------------------------------------------------------------------


@dataclass
class RecordedRequest:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]


class ProfileServer:
    """In-process PostgREST for `profiles`. Rows are keyed by id; `status` forces an error."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.requests: list[RecordedRequest] = []
        self.status = 200
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802  # http.server API
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                owner.requests.append(
                    RecordedRequest(
                        "GET",
                        parsed.path,
                        query,
                        {name.lower(): value for name, value in self.headers.items()},
                    )
                )
                if owner.status != 200:
                    self._send(owner.status, {"code": "XX000", "message": "internal-detail"})
                elif parsed.path != "/rest/v1/profiles":
                    self._send(404, {"code": "PGRST125", "message": "not found"})
                else:
                    wanted = query.get("id", [""])[0].removeprefix("eq.")
                    found = [row for key, row in owner.rows.items() if key == wanted]
                    self._send(200, found)

            def _send(self, status: int, body: object) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def add_profile(
        self,
        user_id: uuid.UUID,
        *,
        email: str = "person@example.test",
        full_name: str = "Test Person",
        role: str = "marketer",
        is_active: bool = True,
    ) -> dict[str, Any]:
        row = {
            "id": str(user_id),
            "email": email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
        }
        self.rows[str(user_id)] = row
        return row


# --- Supabase service client (CLI commands) ----------------------------------------------------


@dataclass
class FakeUser:
    id: str
    email: str
    full_name: str = ""
    password: str | None = None
    confirmed: bool = False


@dataclass
class _Query:
    fake: "FakeServiceClient"
    op: str = "select"
    columns: list[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    filters: list[tuple[str, Any]] = field(default_factory=list)
    max_rows: int | None = None

    def select(self, columns: str = "*") -> "_Query":
        self.op = "select"
        self.columns = [name.strip() for name in columns.split(",")]
        return self

    def update(self, values: dict[str, Any]) -> "_Query":
        self.op = "update"
        self.values = values
        return self

    def eq(self, column: str, value: Any) -> "_Query":
        self.filters.append((column, value))
        return self

    def ilike(self, column: str, value: str) -> "_Query":
        return self.eq(column, value.lower())

    def limit(self, count: int) -> "_Query":
        self.max_rows = count
        return self

    def execute(self) -> SimpleNamespace:
        rows = [
            row
            for row in self.fake.profiles.values()
            if all(str(row.get(column)) == str(value) for column, value in self.filters)
        ]
        if self.max_rows is not None:
            rows = rows[: self.max_rows]
        if self.op == "update":
            for row in rows:
                self.fake.apply_profile_update(row, self.values)
            return SimpleNamespace(data=[dict(row) for row in rows])
        columns = [name for name in self.columns if name != "*"]
        return SimpleNamespace(
            data=[{name: row[name] for name in columns} if columns else dict(row) for row in rows]
        )


class FakeServiceClient:
    """Service-role client double. `calls` records every side effect in order.

    Rules copied from the database: a new auth user gets a `marketer` profile (trigger); the last
    active administrator can neither be demoted nor deactivated (`LAST_ADMIN`).
    `errors` maps a method name to an exception raised when it is called.
    """

    def __init__(self) -> None:
        self.users: dict[str, FakeUser] = {}
        self.profiles: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[Any, ...]] = []
        self.errors: dict[str, Exception] = {}
        self.last_hashed_token = ""
        self.auth = SimpleNamespace(admin=self._admin())

    # -- setup helpers for tests --

    def seed(
        self,
        email: str,
        *,
        role: str = "marketer",
        confirmed: bool = True,
        is_active: bool = True,
        full_name: str = "Seeded",
    ) -> FakeUser:
        user = FakeUser(str(uuid.uuid4()), email.lower(), full_name, confirmed=confirmed)
        self.users[user.id] = user
        self.profiles[user.id] = {
            "id": user.id,
            "email": user.email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
        }
        return user

    def user_by_email(self, email: str) -> FakeUser | None:
        return next((u for u in self.users.values() if u.email == email.lower()), None)

    def profile_of(self, email: str) -> dict[str, Any]:
        user = self.user_by_email(email)
        assert user is not None, f"no auth user for {email}"
        return self.profiles[user.id]

    def calls_named(self, name: str) -> list[tuple[Any, ...]]:
        return [call for call in self.calls if call[0] == name]

    # -- the client surface --

    def table(self, name: str) -> _Query:
        assert name == "profiles", f"unexpected table {name}"
        return _Query(self)

    def apply_profile_update(self, row: dict[str, Any], values: dict[str, Any]) -> None:
        demotes = row["role"] == "admin" and values.get("role", "admin") != "admin"
        deactivates = row["is_active"] and values.get("is_active", True) is False
        if row["role"] == "admin" and row["is_active"] and (demotes or deactivates):
            others = [
                p
                for p in self.profiles.values()
                if p is not row and p["role"] == "admin" and p["is_active"]
            ]
            if not others:
                raise APIError(
                    {"message": "LAST_ADMIN", "code": "P0001", "details": "", "hint": ""}
                )
        self.calls.append(("profile_update", row["id"], dict(values)))
        row.update(values)

    def _add_user(self, email: str, full_name: str, **extra: Any) -> FakeUser:
        user = FakeUser(str(uuid.uuid4()), email.lower(), full_name, **extra)
        self.users[user.id] = user
        self.profiles[user.id] = {
            "id": user.id,
            "email": user.email,
            "full_name": full_name,
            "role": "marketer",
            "is_active": True,
        }
        return user

    def _admin(self) -> SimpleNamespace:  # noqa: C901
        fake = self

        def guard(name: str) -> None:
            if name in fake.errors:
                raise fake.errors[name]

        def invite_user_by_email(email: str, options: dict[str, Any] | None = None) -> Any:
            guard("invite_user_by_email")
            fake.calls.append(("invite", email, options or {}))
            existing = fake.user_by_email(email)
            if existing is not None and existing.confirmed:
                raise AuthApiError("A user with this email address exists", 422, "email_exists")  # type: ignore[arg-type]
            full_name = ((options or {}).get("data") or {}).get("full_name", "")
            user = existing or fake._add_user(email, full_name)
            return SimpleNamespace(user=SimpleNamespace(id=user.id, email=user.email))

        def generate_link(params: dict[str, Any]) -> Any:
            guard("generate_link")
            fake.calls.append(("generate_link", dict(params)))
            email = params["email"]
            existing = fake.user_by_email(email)
            if existing is not None and existing.confirmed:
                raise AuthApiError("A user with this email address exists", 422, "email_exists")  # type: ignore[arg-type]
            full_name = ((params.get("options") or {}).get("data") or {}).get("full_name", "")
            user = existing or fake._add_user(email, full_name)
            fake.last_hashed_token = secrets.token_hex(28)
            return SimpleNamespace(
                properties=SimpleNamespace(
                    action_link=f"http://supabase.test/auth/v1/verify?token={fake.last_hashed_token}",
                    email_otp="000000",
                    hashed_token=fake.last_hashed_token,
                    redirect_to="",
                    verification_type="invite",
                ),
                user=SimpleNamespace(id=user.id, email=user.email),
            )

        def create_user(attributes: dict[str, Any]) -> Any:
            guard("create_user")
            email = attributes["email"].lower()
            fake.calls.append(("create_user", email, dict(attributes)))
            if fake.user_by_email(email) is not None:
                raise AuthApiError("A user with this email address exists", 422, "email_exists")  # type: ignore[arg-type]
            full_name = (attributes.get("user_metadata") or {}).get("full_name", "")
            user = fake._add_user(
                email,
                full_name,
                password=attributes.get("password"),
                confirmed=bool(attributes.get("email_confirm")),
            )
            return SimpleNamespace(user=SimpleNamespace(id=user.id, email=user.email))

        def update_user_by_id(uid: str, attributes: dict[str, Any]) -> Any:
            guard("update_user_by_id")
            fake.calls.append(("update_user", fake.users[uid].email, dict(attributes)))
            user = fake.users[uid]
            if "password" in attributes:
                user.password = attributes["password"]
            if attributes.get("email_confirm"):
                user.confirmed = True
            return SimpleNamespace(user=SimpleNamespace(id=user.id, email=user.email))

        def get_user_by_id(uid: str) -> Any:
            guard("get_user_by_id")
            user = fake.users[uid]
            return SimpleNamespace(
                user=SimpleNamespace(
                    id=user.id,
                    email=user.email,
                    email_confirmed_at="2026-10-03T10:00:00Z" if user.confirmed else None,
                )
            )

        def list_users(*_: Any, **__: Any) -> list[Any]:
            guard("list_users")
            return [
                SimpleNamespace(
                    id=u.id,
                    email=u.email,
                    email_confirmed_at="2026-10-03T10:00:00Z" if u.confirmed else None,
                )
                for u in fake.users.values()
            ]

        return SimpleNamespace(
            invite_user_by_email=invite_user_by_email,
            generate_link=generate_link,
            create_user=create_user,
            update_user_by_id=update_user_by_id,
            get_user_by_id=get_user_by_id,
            list_users=list_users,
        )

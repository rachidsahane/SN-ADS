"""Test doubles shared by the phase 2 tests (no network, no new dependency).

- `FakeRedis`: a dict with TTLs that can be told to fail like a Redis outage.
- `ProfileServer`: a tiny in-process PostgREST that answers `GET /rest/v1/profiles`. The real
  supabase-py client talks to it, so tests stay independent from how the code under test builds
  its calls (and prove which token and key are sent).
- `FakeServiceClient`: the part of the service-role Supabase client used by the CLI commands
  (gotrue admin API + the `profiles` table), with the database trigger rules that matter.

Phase 3 adds: `FakeUserDb` (the user-token Supabase client double: profiles + audit_log + rpc, with
the RLS-like rules the API relies on), a paginated gotrue admin namespace on `FakeServiceClient`,
`AdminWorld` (one acting administrator wired to all the doubles) and a PostgREST double that also
answers PATCH, rpc and `audit_log`.

Every secret-looking value is assembled at run time, never written as a literal, so that scanners
and the S105/S106 lint rules have nothing to flag.
"""

import json
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse

from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

from app.infra.profile_cache import ProfileCache
from app.schemas.user import CurrentUser

# 70 bytes: long enough for HS512 too (PyJWT warns, and pytest turns warnings into errors, when a
# key is shorter than the hash size while the HS512 test token is signed).
JWT_SECRET = "test-only-" + "k" * 60
OTHER_JWT_SECRET = "other-test-" + "z" * 40
JWT_ISSUER = "http://supabase.test/auth/v1"
WEB_APP_URL = "http://localhost:3000"
UNREACHABLE_URL = "http://127.0.0.1:9"  # discard port: connection refused at once
UNREACHABLE_REDIS = "redis://127.0.0.1:9/0"


def random_value(prefix: str = "v") -> str:
    return f"{prefix}-{secrets.token_hex(12)}"


def log_entries(out: str) -> list[dict[str, Any]]:
    """The JSON log lines of a captured stdout."""
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def reported_errors(out: str) -> list[dict[str, Any]]:
    """The errors reported with `capture()` in a captured stdout (event `unexpected_error`)."""
    return [entry for entry in log_entries(out) if entry["event"] == "unexpected_error"]


# --- Redis -------------------------------------------------------------------------------------


class FakeRedis:
    """Enough of redis.Redis for the profile cache. `error` makes every call raise it."""

    def __init__(self, *, error: Exception | None = None, events: list[str] | None = None) -> None:
        self.error = error
        self.events = events  # optional shared, ordered log of side effects (phase 3)
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
        if self.events is not None:
            self.events.append("cache.invalidate")
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
    body: Any = None


class _PostgrestHandler(BaseHTTPRequestHandler):
    """Request handler of `ProfileServer`; `owner` is set on a subclass made per server."""

    owner: "ProfileServer"

    def _record(self, method: str) -> tuple[Any, dict[str, list[str]]]:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else None
        self.owner.requests.append(
            RecordedRequest(
                method,
                parsed.path,
                query,
                {name.lower(): value for name, value in self.headers.items()},
                body,
            )
        )
        return body, query

    def do_GET(self) -> None:  # noqa: N802  # http.server API
        _, query = self._record("GET")
        path = urlparse(self.path).path
        if self.owner.status != 200:
            self._send(self.owner.status, self.owner.error_body)
        elif path == "/rest/v1/audit_log":
            self._send(200, self.owner.audit_rows)
        elif path != "/rest/v1/profiles":
            self._send(404, {"code": "PGRST125", "message": "not found"})
        else:
            self._send(200, self.owner._select(query))

    def do_PATCH(self) -> None:  # noqa: N802  # http.server API
        body, query = self._record("PATCH")
        if self.owner.status != 200:
            self._send(self.owner.status, self.owner.error_body)
        elif urlparse(self.path).path != "/rest/v1/profiles":
            self._send(404, {"code": "PGRST125", "message": "not found"})
        elif self.owner.refuse_updates:
            self._send(200, [])
        else:
            updated = self.owner._select(query)
            for row in updated:
                row.update(body or {})
            self._send(200, updated)

    def do_POST(self) -> None:  # noqa: N802  # http.server API
        self._record("POST")
        if self.owner.status != 200:
            self._send(self.owner.status, self.owner.error_body)
        elif urlparse(self.path).path != "/rest/v1/rpc/log_audit":
            self._send(404, {"code": "PGRST125", "message": "not found"})
        else:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def _send(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


class ProfileServer:
    """In-process PostgREST. Rows of `profiles` are keyed by id; `status` forces an error.

    Phase 3: it also answers `GET` with an `email` filter or no filter, `PATCH /profiles`
    (representation of the updated rows, `refuse_updates` models an RLS refusal), `GET /audit_log`
    (`audit_rows` are returned as they are) and `POST /rpc/log_audit` (recorded in `requests`).
    """

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.audit_rows: list[dict[str, Any]] = []
        self.requests: list[RecordedRequest] = []
        self.status = 200
        self.error_body: dict[str, Any] = {"code": "XX000", "message": "internal-detail"}
        self.refuse_updates = False
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), type("Handler", (_PostgrestHandler,), {"owner": self})
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _select(self, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        if "id" in query:
            wanted = query["id"][0].removeprefix("eq.")
            return [row for key, row in self.rows.items() if key == wanted]
        if "email" in query:
            wanted = query["email"][0].removeprefix("eq.")
            return [row for row in self.rows.values() if row["email"] == wanted]
        return list(self.rows.values())

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def add_profile(  # noqa: PLR0913
        self,
        user_id: uuid.UUID,
        *,
        email: str = "person@example.test",
        full_name: str = "Test Person",
        role: str = "marketer",
        is_active: bool = True,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": str(user_id),
            "email": email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
        }
        if created_at is not None:
            row["created_at"] = created_at
        self.rows[str(user_id)] = row
        return row


BASE_TIME = datetime(2026, 10, 3, 10, 0, 0, 123456, tzinfo=UTC)


def stamp(tick: int) -> str:
    """The `tick`-th second after BASE_TIME as PostgREST prints it (microseconds, +00:00)."""
    return (BASE_TIME + timedelta(seconds=tick)).isoformat()


def check_last_admin(
    profiles: dict[str, dict[str, Any]], row: dict[str, Any], values: dict[str, Any]
) -> None:
    """The `guard_last_admin` trigger: the last active administrator can neither be demoted nor
    deactivated (the final state of ONE statement is what counts)."""
    demotes = row["role"] == "admin" and values.get("role", "admin") != "admin"
    deactivates = row["is_active"] and values.get("is_active", True) is False
    if row["role"] == "admin" and row["is_active"] and (demotes or deactivates):
        others = [
            p for p in profiles.values() if p is not row and p["role"] == "admin" and p["is_active"]
        ]
        if not others:
            raise APIError({"message": "LAST_ADMIN", "code": "P0001", "details": "", "hint": ""})


# --- Supabase service client (CLI commands) ----------------------------------------------------


@dataclass
class FakeUser:
    id: str
    email: str
    full_name: str = ""
    password: str | None = None
    confirmed: bool = False
    banned: bool = False


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
        # Phase 3. `late_errors`: the side effect happens, THEN the call raises (a gotrue 5xx after
        # the user was created). `events`: ordered log shared with the other doubles.
        self.late_errors: dict[str, Exception] = {}
        self.events: list[str] = []
        self.created_at: dict[str, str] = {}
        self.list_users_cap: int | None = None  # server-side cap on `per_page`
        self._ticks = 0
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
        self.created_at[user.id] = self.tick()
        self.profiles[user.id] = {
            "id": user.id,
            "email": user.email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
        }
        return user

    def tick(self) -> str:
        """A strictly increasing timestamp with microseconds, like PostgREST returns them."""
        self._ticks += 1
        return stamp(self._ticks)

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
        check_last_admin(self.profiles, row, values)
        self.calls.append(("profile_update", row["id"], dict(values)))
        row.update(values)

    def _add_user(self, email: str, full_name: str, **extra: Any) -> FakeUser:
        user = FakeUser(str(uuid.uuid4()), email.lower(), full_name, **extra)
        self.users[user.id] = user
        self.created_at[user.id] = self.tick()
        self.profiles[user.id] = {
            "id": user.id,
            "email": user.email,
            "full_name": full_name,
            "role": "marketer",
            "is_active": True,
        }
        return user

    def _admin(self) -> SimpleNamespace:  # noqa: C901, PLR0915
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
            fake.events.append("invite")
            if "invite_user_by_email" in fake.late_errors:
                raise fake.late_errors["invite_user_by_email"]
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
            user = fake.users[uid]
            if "ban_duration" in attributes:  # phase 3: deactivation / reactivation
                value = attributes["ban_duration"]
                fake.calls.append(("ban", uid, value))
                fake.events.append("unban" if value == "none" else "ban")
                user.banned = value != "none"
                return SimpleNamespace(user=SimpleNamespace(id=user.id, email=user.email))
            fake.calls.append(("update_user", fake.users[uid].email, dict(attributes)))
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

        def list_users(page: int | None = None, per_page: int | None = None) -> list[Any]:
            guard("list_users")
            fake.calls.append(("gotrue_list", page, per_page))
            everyone = list(fake.users.values())
            if page is not None and per_page is not None:
                size = min(per_page, fake.list_users_cap or per_page)
                everyone = everyone[(page - 1) * size : page * size]
            return [
                SimpleNamespace(
                    id=u.id,
                    email=u.email,
                    email_confirmed_at="2026-10-03T10:00:00Z" if u.confirmed else None,
                )
                for u in everyone
            ]

        def delete_user(uid: str, should_soft_delete: bool = False) -> None:
            guard("delete_user")
            fake.calls.append(("delete_user", uid))
            fake.events.append("delete_user")
            fake.users.pop(uid, None)
            fake.profiles.pop(uid, None)

        return SimpleNamespace(
            invite_user_by_email=invite_user_by_email,
            generate_link=generate_link,
            create_user=create_user,
            update_user_by_id=update_user_by_id,
            get_user_by_id=get_user_by_id,
            list_users=list_users,
            delete_user=delete_user,
        )


# --- Supabase user client (admin routes) -------------------------------------------------------

_KEYSET = re.compile(
    r"^created_at\.lt\.(?P<c>[^,]+),and\(created_at\.eq\.(?P=c),id\.lt\.(?P<i>[^)]+)\)$"
)
_EMBED = re.compile(r"(?P<alias>\w+):(?P<table>\w+)(?:!(?P<hint>\w+))?\((?P<columns>[^)]*)\)")
_UPDATABLE = frozenset({"full_name", "role", "is_active"})
_DIGITS = re.compile(r"^\d+$")


def _sort_key(column: str, value: Any) -> Any:
    if column == "created_at":
        return datetime.fromisoformat(str(value))
    return int(value) if _DIGITS.match(str(value)) else str(value)


@dataclass
class _UserQuery:
    """The query builder of `FakeUserDb.table(...)`, with the RLS-like rules of the database."""

    db: "FakeUserDb"
    table: str
    op: str = "select"
    columns: str = "*"
    values: dict[str, Any] = field(default_factory=dict)
    filters: list[tuple[str, str]] = field(default_factory=list)
    orders: list[tuple[str, bool]] = field(default_factory=list)
    max_rows: int | None = None
    keyset: str | None = None

    def select(self, columns: str = "*") -> "_UserQuery":
        self.op, self.columns = "select", columns
        return self

    def update(self, values: dict[str, Any]) -> "_UserQuery":
        self.op, self.values = "update", dict(values)
        return self

    def eq(self, column: str, value: Any) -> "_UserQuery":
        self.filters.append((column, str(value)))
        return self

    def order(self, column: str, *, desc: bool = False) -> "_UserQuery":
        self.orders.append((column, desc))
        return self

    def limit(self, count: int) -> "_UserQuery":
        self.max_rows = count
        return self

    def or_(self, expression: str) -> "_UserQuery":
        # Only the keyset form is legitimate: anything else reaching the database is a bug.
        assert _KEYSET.match(expression), f"unexpected or_ filter: {expression}"
        self.keyset = expression
        return self

    # -- execution --

    def execute(self) -> SimpleNamespace:
        name = f"{self.table}.{self.op}"
        self.db.calls.append(self._call(name))
        if name in self.db.errors:
            raise self.db.errors[name]
        if self.table == "profiles":
            return SimpleNamespace(data=self._profiles())
        assert self.table == "audit_log", f"unexpected table {self.table}"
        return SimpleNamespace(data=self._audit_log())

    def _call(self, name: str) -> tuple[Any, ...]:
        if self.op == "update":
            target = next((v for c, v in self.filters if c == "id"), None)
            return (name, target, dict(self.values))
        return (
            name,
            {
                "columns": self.columns,
                "filters": list(self.filters),
                "orders": list(self.orders),
                "limit": self.max_rows,
                "or": self.keyset,
            },
        )

    def _profiles(self) -> list[dict[str, Any]]:
        db = self.db
        rows = [db.full_row(r) for r in db.profiles.values() if self._matches(db.full_row(r))]
        if self.op == "update":
            return self._update(rows)
        rows = [row for row in rows if db.can_read_profile(row)]
        return self._shape(self._page(rows), self.columns)

    def _matches(self, row: dict[str, Any]) -> bool:
        return all(str(row.get(column)) == value for column, value in self.filters)

    def _update(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        db = self.db
        if not db.caller_is_admin() or db.vanish_on_update:
            return []
        if set(self.values) - _UPDATABLE:  # `email`, `id`: no column grant
            raise APIError(
                {"message": "permission denied for table profiles", "code": "42501",
                 "details": "", "hint": ""}
            )  # fmt: skip
        updated = []
        for row in rows:
            if row["id"] == db.caller_id:  # RLS: `id <> auth.uid()`, silently zero rows
                continue
            check_last_admin(db.profiles, db.profiles[row["id"]], self.values)
            db.profiles[row["id"]].update(self.values)
            db.events.append("db.update")
            updated.append(db.full_row(db.profiles[row["id"]]))
        return updated

    def _page(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for column, desc in reversed(self.orders):
            rows.sort(key=lambda row, c=column: _sort_key(c, row[c]), reverse=desc)  # type: ignore[misc]
        if self.keyset is not None:
            found = _KEYSET.match(self.keyset)
            assert found is not None
            created_at = datetime.fromisoformat(found["c"])
            row_id = _sort_key("id", found["i"])
            rows = [
                row
                for row in rows
                if _sort_key("created_at", row["created_at"]) < created_at
                or (
                    _sort_key("created_at", row["created_at"]) == created_at
                    and _sort_key("id", row["id"]) < row_id
                )
            ]
        return rows[: self.max_rows] if self.max_rows is not None else rows

    @staticmethod
    def _shape(rows: list[dict[str, Any]], columns: str) -> list[dict[str, Any]]:
        wanted = [name.strip() for name in columns.split(",") if name.strip() not in {"", "*"}]
        return [{n: row[n] for n in wanted} if wanted else dict(row) for row in rows]

    def _audit_log(self) -> list[dict[str, Any]]:
        db = self.db
        if not db.caller_is_admin():
            return []
        embed = _EMBED.search(self.columns)
        plain = _EMBED.sub("", self.columns) if embed else self.columns
        rows = [r for r in db.audit if all(str(r.get(c)) == v for c, v in self.filters)]
        out = self._shape(self._page([dict(r) for r in rows]), plain)
        if embed is not None:
            by_id = {row["id"]: row for row in out}
            for source in rows:
                if source["id"] in by_id:
                    actor = db.profiles.get(str(source["actor_id"]))
                    cols = [c.strip() for c in embed["columns"].split(",")]
                    by_id[source["id"]][embed["alias"]] = (
                        {c: actor[c] for c in cols} if actor else None
                    )
        return out


class _Rpc:
    def __init__(self, db: "FakeUserDb", name: str, params: dict[str, Any]) -> None:
        self.db, self.name, self.params = db, name, params

    def execute(self) -> SimpleNamespace:
        db = self.db
        db.calls.append(("rpc", self.name, dict(self.params)))
        key = f"rpc.{self.name}"
        if key in db.errors:
            raise db.errors[key]
        assert self.name == "log_audit", f"unexpected rpc {self.name}"
        assert set(self.params) == {"p_action", "p_target_type", "p_target_id", "p_metadata"}
        if not db.caller_is_admin():
            raise APIError({"message": "FORBIDDEN", "code": "P0001", "details": "", "hint": ""})
        db.add_audit(
            action=self.params["p_action"],
            target_type=self.params["p_target_type"],
            target_id=self.params["p_target_id"],
            metadata=self.params["p_metadata"],
            actor_id=db.caller_id,
        )
        db.events.append("audit")
        return SimpleNamespace(data=[])


class FakeUserDb:
    """The Supabase client built with the CALLER's token (RLS applies), as a double.

    Profiles live in the `FakeServiceClient` (same dict: the gotrue trigger creates the profile
    row); `created_at` comes from it. Rules copied from the database: an admin reads and updates
    every profile but its own (silent zero rows), only `full_name, role, is_active` are
    updatable, `guard_last_admin`, `log_audit` is admin only, `audit_log` is readable by admins.
    `errors` maps "profiles.select", "profiles.update", "audit_log.select" or "rpc.log_audit" to
    an exception raised on execute. `calls` records every request, `events` the writes.
    """

    def __init__(self, service: FakeServiceClient, *, caller_id: str | uuid.UUID) -> None:
        self.service = service
        self.caller_id = str(caller_id)
        self.profiles = service.profiles
        self.errors: dict[str, Exception] = {}
        self.calls: list[tuple[Any, ...]] = []
        self.events = service.events
        self.audit: list[dict[str, Any]] = []
        self.vanish_on_update = False  # the row disappears between the read and the update
        self.fixed_audit_time: str | None = None  # every new audit row gets this created_at
        self._audit_ticks = 1000

    def calls_named(self, name: str) -> list[tuple[Any, ...]]:
        return [call for call in self.calls if call[0] == name]

    def full_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "created_at": self.service.created_at.get(row["id"], stamp(0))}

    def caller_is_admin(self) -> bool:
        caller = self.profiles.get(self.caller_id)
        return bool(caller and caller["role"] == "admin" and caller["is_active"])

    def can_read_profile(self, row: dict[str, Any]) -> bool:
        caller = self.profiles.get(self.caller_id)
        if caller is None or not caller["is_active"]:
            return False
        return caller["role"] == "admin" or row["id"] == self.caller_id

    def table(self, name: str) -> _UserQuery:
        return _UserQuery(self, name)

    def rpc(self, name: str, params: dict[str, Any]) -> _Rpc:
        return _Rpc(self, name, params)

    def add_audit(  # noqa: PLR0913
        self,
        *,
        action: str,
        target_id: str,
        target_type: str = "user",
        metadata: dict[str, Any] | None = None,
        actor_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        self._audit_ticks += 1
        row = {
            "id": len(self.audit) + 1,
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": dict(metadata or {}),
            "created_at": created_at or self.fixed_audit_time or stamp(self._audit_ticks),
        }
        self.audit.append(row)
        return row


@dataclass
class AdminWorld:
    """One acting administrator wired to every double. `events` is the ordered log of effects."""

    service: FakeServiceClient
    db: FakeUserDb
    redis: FakeRedis
    cache: ProfileCache
    admin: FakeUser
    events: list[str]

    @property
    def actor(self) -> CurrentUser:
        return CurrentUser(
            id=uuid.UUID(self.admin.id),
            role="admin",
            access_token="admin-token-value",  # noqa: S106
        )


def make_admin_world(admin_email: str = "boss@example.test") -> AdminWorld:
    service = FakeServiceClient()
    admin = service.seed(admin_email, role="admin", full_name="Boss Admin")
    db = FakeUserDb(service, caller_id=admin.id)
    redis = FakeRedis(events=service.events)
    return AdminWorld(
        service=service,
        db=db,
        redis=redis,
        cache=ProfileCache(redis),  # type: ignore[arg-type]
        admin=admin,
        events=service.events,
    )

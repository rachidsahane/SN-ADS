"""Administration of users: list, invite, change role, deactivate, reactivate (API_SPEC 6.6).

The ONLY service of this phase that holds the service-role client (ARCHITECTURE 2.5): it is needed
for the Auth admin API (invitation, ban, listing of confirmation dates, rollback). Every access to
`profiles` and `audit_log` uses the ADMINISTRATOR's own client, so RLS stays the second barrier.

Order of effects of a change (D-085): database flag, Auth ban, cache invalidation, audit entry.
"""

import uuid
from collections.abc import Mapping
from typing import Final

import httpx

# Not re-exported by `gotrue`: the module path is the only way to name the admin API type.
from gotrue._sync.gotrue_admin_api import SyncGoTrueAdminAPI
from postgrest.exceptions import APIError
from supabase import AuthApiError, AuthError, Client

from app.api.errors import (
    EMAIL_EXISTS_MESSAGE,
    FORBIDDEN_MESSAGE,
    SELF_ACTION_MESSAGE,
    UNAVAILABLE_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    AppError,
    ErrorCode,
    from_postgrest,
)
from app.config import Settings
from app.infra.observability import capture
from app.infra.pagination import Page, encode_cursor, require_cursor_id
from app.infra.profile_cache import ProfileCache
from app.infra.redis_client import CACHE_ERRORS
from app.infra.supabase_clients import get_service_client
from app.repositories.profiles_repo import (
    find_profile_by_email,
    get_profile_record,
    list_profile_records,
    update_profile,
)
from app.schemas.common import ErrorDetail
from app.schemas.user import (
    AdminUser,
    AdminUserPage,
    CurrentUser,
    InviteUserRequest,
    ProfileRecord,
    UpdateUserRequest,
    UserStatus,
)
from app.services import audit_service

BAN_DURATION: Final = "876000h"  # about 100 years: gotrue has no "forever"
UNBAN_DURATION: Final = "none"
_AUTH_PAGE_SIZE: Final = 200
_MAX_AUTH_PAGES: Final = 50
_RATE_LIMIT_MESSAGE: Final = "Too many requests. Please wait a moment."
_EMAIL_INVALID_MESSAGE: Final = "Email is not valid."
_REFUSED_ADDRESS_CODES: Final = frozenset({"validation_failed", "email_address_invalid"})
_NO_FIELD_MESSAGE: Final = "Provide at least one field to update: role, is_active or full_name."
_BACKEND_ERRORS: Final = (httpx.HTTPError, httpx.InvalidURL, APIError, AuthError)
_DATABASE_ERRORS: Final = (httpx.HTTPError, httpx.InvalidURL, APIError)


class _UnexpectedStateError(RuntimeError):
    """An update that the database accepted but that changed no row."""


def _auth_admin(settings: Settings) -> SyncGoTrueAdminAPI:
    return get_service_client(settings).auth.admin


def _unavailable(error: BaseException, operation: str, **ids: str) -> AppError:
    """Report the failure (operation and ids only, never an e-mail or a name), build the 503."""
    capture(error, operation=operation, **ids)
    return AppError(ErrorCode.SERVICE_UNAVAILABLE, 503, UNAVAILABLE_MESSAGE)


def _confirmed_user_ids(admin: SyncGoTrueAdminAPI) -> set[str]:
    """Ids of the users who opened their invitation link. gotrue may cap `per_page`, so only an
    EMPTY page ends the loop."""
    confirmed: set[str] = set()
    for number in range(1, _MAX_AUTH_PAGES + 1):
        users = admin.list_users(page=number, per_page=_AUTH_PAGE_SIZE)
        if not users:
            break
        confirmed.update(str(user.id) for user in users if user.email_confirmed_at is not None)
    return confirmed


def _status(profile: ProfileRecord, confirmed: bool) -> UserStatus:
    """A deactivated user is never "invited", whatever its confirmation state."""
    if not profile.is_active:
        return "deactivated"
    return "active" if confirmed else "invited"


def _admin_user(profile: ProfileRecord, status: UserStatus) -> AdminUser:
    return AdminUser(**profile.model_dump(), status=status)


# --- list ---------------------------------------------------------------------------------------


def list_users(db: Client, *, settings: Settings, page: Page) -> AdminUserPage:
    """Users newest first, with their status. One extra row tells if a page follows."""
    require_cursor_id(page.after, "uuid")
    try:
        rows = list_profile_records(db, limit=page.limit + 1, after=page.after)
        confirmed = _confirmed_user_ids(_auth_admin(settings))
    except _BACKEND_ERRORS as error:
        raise _unavailable(error, "list_users") from None
    kept = rows[: page.limit]
    next_cursor = (
        encode_cursor(kept[-1].created_at, kept[-1].id) if len(rows) > page.limit else None
    )
    items = [_admin_user(row, _status(row, str(row.id) in confirmed)) for row in kept]
    return AdminUserPage(items=items, next_cursor=next_cursor)


# --- invite -------------------------------------------------------------------------------------


def _delete_auth_user(admin: SyncGoTrueAdminAPI, user_id: str) -> None:
    """Best effort: a failed rollback is reported, the caller still answers its own error."""
    try:
        admin.delete_user(user_id)
    except _BACKEND_ERRORS as error:
        capture(error, operation="rollback_invite", user_id=user_id)


def _rollback_invite(admin: SyncGoTrueAdminAPI, db: Client, email: str) -> None:
    """Undo an invitation that failed half way. The e-mail had no profile before the call, so a
    profile found now was created by it."""
    try:
        found = find_profile_by_email(db, email)
    except _DATABASE_ERRORS as error:
        capture(error, operation="rollback_invite")
        return
    if found is not None:
        _delete_auth_user(admin, str(found.id))


def _invite_refusal(error: AuthError) -> AppError | None:
    """The business answer to a gotrue refusal, or None when it is a plain backend failure."""
    if isinstance(error, AuthApiError):
        if error.code == "email_exists":  # a concurrent invitation won the race
            return AppError(ErrorCode.EMAIL_ALREADY_REGISTERED, 409, EMAIL_EXISTS_MESSAGE)
        if error.status == httpx.codes.TOO_MANY_REQUESTS:
            return AppError(
                ErrorCode.RATE_LIMITED, 429, _RATE_LIMIT_MESSAGE, headers={"Retry-After": "60"}
            )
        if (
            error.code in _REFUSED_ADDRESS_CODES
        ):  # stricter than our own pattern: the typo is theirs
            return AppError(
                ErrorCode.VALIDATION_ERROR,
                422,
                "Some fields are invalid.",
                [
                    ErrorDetail(
                        field="email", issue="invalid_format", message=_EMAIL_INVALID_MESSAGE
                    )
                ],
            )
    return None


def _send_invitation(
    admin: SyncGoTrueAdminAPI, db: Client, payload: InviteUserRequest, web_app_url: str
) -> uuid.UUID:
    """Create the Auth user and send the e-mail; returns the new user id."""
    options = {
        "data": {"full_name": payload.full_name},
        "redirect_to": f"{web_app_url}/auth/confirm",
    }
    try:
        response = admin.invite_user_by_email(payload.email, options)  # type: ignore[arg-type]
        if response.user is None:
            raise _UnexpectedStateError("gotrue answered without a user")
    except (*_BACKEND_ERRORS, _UnexpectedStateError) as error:
        refusal = _invite_refusal(error) if isinstance(error, AuthError) else None
        if refusal is not None:
            raise refusal from None
        _rollback_invite(admin, db, payload.email)
        raise _unavailable(error, "invite_user") from None
    return uuid.UUID(response.user.id)


def _promote(
    admin: SyncGoTrueAdminAPI, db: Client, user_id: uuid.UUID, role: str
) -> ProfileRecord | None:
    """Give a role to the invited user, with the admin's token (never through Auth metadata,
    SEC-04). Any failure undoes the invitation."""
    if role != "admin":
        return None
    try:
        promoted = update_profile(db, user_id, {"role": role})
        if promoted is None:
            raise _UnexpectedStateError("the invited profile was not updated")
    except (*_DATABASE_ERRORS, _UnexpectedStateError) as error:
        _delete_auth_user(admin, str(user_id))
        raise _unavailable(error, "promote_invited_user", user_id=str(user_id)) from None
    return promoted


def _read_invited(db: Client, user_id: uuid.UUID, promoted: ProfileRecord | None) -> ProfileRecord:
    try:
        profile = promoted or get_profile_record(db, user_id)
        if profile is None:
            raise _UnexpectedStateError("the invited profile is not readable")
    except (*_DATABASE_ERRORS, _UnexpectedStateError) as error:
        raise _unavailable(error, "read_invited_user", user_id=str(user_id)) from None
    return profile


def _require_admin_in_database(actor: CurrentUser, db: Client) -> None:
    """The invitation is sent with the SERVICE key, which no RLS policy guards. The role of the
    actor comes from the 60 s profile cache (it may be stale if an invalidation failed or raced),
    so the database confirms it: a deactivated user sees no profile at all, a demoted one sees a
    role other than admin. Every other action of this module is refused by RLS on its own."""
    try:
        own = get_profile_record(db, actor.id)
    except _DATABASE_ERRORS as error:
        raise _unavailable(error, "invite_check_actor") from None
    if own is None or own.role != "admin" or not own.is_active:
        raise AppError(ErrorCode.FORBIDDEN, 403, FORBIDDEN_MESSAGE)


def invite_user(
    actor: CurrentUser, db: Client, payload: InviteUserRequest, *, settings: Settings
) -> AdminUser:
    """Invite a user. Any existing profile (invited, active or deactivated) is a 409 (D-083)."""
    _require_admin_in_database(actor, db)
    try:
        existing = find_profile_by_email(db, payload.email)
    except _DATABASE_ERRORS as error:
        raise _unavailable(error, "invite_check_email") from None
    if existing is not None:
        raise AppError(ErrorCode.EMAIL_ALREADY_REGISTERED, 409, EMAIL_EXISTS_MESSAGE)
    admin = _auth_admin(settings)
    user_id = _send_invitation(admin, db, payload, settings.web_app_url)
    promoted = _promote(admin, db, user_id, payload.role)
    audit_service.record(
        db,
        action="user.invited",
        target_type="user",
        target_id=str(user_id),
        metadata={"email": payload.email, "role": payload.role},
    )
    return _admin_user(_read_invited(db, user_id, promoted), "invited")


# --- update -------------------------------------------------------------------------------------


def _apply_profile_changes(
    db: Client, user_id: uuid.UUID, changes: Mapping[str, object]
) -> ProfileRecord:
    """ONE statement for every changed column, so that the last-administrator trigger sees the
    final state."""
    try:
        updated = update_profile(db, user_id, changes)
    except APIError as error:
        translated = from_postgrest(error)
        if translated is not None:
            raise translated from None
        raise _unavailable(error, "update_user", user_id=str(user_id)) from None
    except httpx.HTTPError as error:
        raise _unavailable(error, "update_user", user_id=str(user_id)) from None
    if updated is None:
        raise AppError(ErrorCode.NOT_FOUND, 404, USER_NOT_FOUND_MESSAGE)
    return updated


def _apply_ban(admin: SyncGoTrueAdminAPI, user_id: uuid.UUID, is_active: bool) -> Exception | None:
    """Ban or unban in Auth. Returns the failure instead of raising: the cache and the audit entry
    must still follow (D-085)."""
    duration = UNBAN_DURATION if is_active else BAN_DURATION
    try:
        admin.update_user_by_id(str(user_id), {"ban_duration": duration})
    except _BACKEND_ERRORS as error:
        return error
    return None


def _invalidate(cache: ProfileCache, user_id: uuid.UUID) -> None:
    """Make the change effective at once. A Redis failure is not fatal: RLS already refuses the
    data of a deactivated user and the 60 s TTL bounds the stale role (D-085)."""
    try:
        cache.invalidate(user_id)
    except CACHE_ERRORS as error:
        capture(error, operation="invalidate_profile_cache", user_id=str(user_id))


def _audit_changes(
    db: Client, user_id: uuid.UUID, before: ProfileRecord, changes: Mapping[str, object]
) -> None:
    target_id = str(user_id)
    if "role" in changes:
        audit_service.record(
            db,
            action="user.role_changed",
            target_type="user",
            target_id=target_id,
            metadata={"email": before.email, "from": before.role, "to": changes["role"]},
        )
    if "is_active" in changes:
        audit_service.record(
            db,
            action="user.reactivated" if changes["is_active"] else "user.deactivated",
            target_type="user",
            target_id=target_id,
            metadata={"email": before.email},
        )


def _final_status(admin: SyncGoTrueAdminAPI, profile: ProfileRecord) -> UserStatus:
    if not profile.is_active:
        return "deactivated"
    try:
        auth_user = admin.get_user_by_id(str(profile.id)).user
    except _BACKEND_ERRORS as error:
        capture(error, operation="read_auth_user", user_id=str(profile.id))
        return "active"  # the page refetches the list and shows the real status
    confirmed = auth_user is not None and auth_user.email_confirmed_at is not None
    return _status(profile, confirmed)


def _effective_changes(
    current: ProfileRecord, requested: Mapping[str, object]
) -> dict[str, object]:
    """The requested values that differ from the current row: the others are no-ops."""
    return {name: value for name, value in requested.items() if getattr(current, name) != value}


def update_user(  # noqa: PLR0913  # signature fixed by LLD 2: the five collaborators are explicit
    actor: CurrentUser,
    db: Client,
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    *,
    settings: Settings,
    cache: ProfileCache,
) -> AdminUser:
    """Change the role, the activity or the name of ANOTHER user."""
    requested = payload.model_dump(exclude_none=True)
    if not requested:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            422,
            "Some fields are invalid.",
            [ErrorDetail(field="body", issue="required", message=_NO_FIELD_MESSAGE)],
        )
    if user_id == actor.id:  # RLS refuses the own row silently (zero rows): say it explicitly
        raise AppError(ErrorCode.SELF_ACTION_FORBIDDEN, 409, SELF_ACTION_MESSAGE)
    try:
        current = get_profile_record(db, user_id)
    except _DATABASE_ERRORS as error:
        raise _unavailable(error, "read_user", user_id=str(user_id)) from None
    if current is None:
        raise AppError(ErrorCode.NOT_FOUND, 404, USER_NOT_FOUND_MESSAGE)
    changes = _effective_changes(current, requested)
    updated = _apply_profile_changes(db, user_id, changes) if changes else current
    admin = _auth_admin(settings)
    ban_error = None
    if "is_active" in requested:  # also when unchanged: a retry repairs a half-done change
        ban_error = _apply_ban(admin, user_id, bool(requested["is_active"]))
    if "role" in changes or "is_active" in requested:
        _invalidate(cache, user_id)
    _audit_changes(db, user_id, current, changes)
    if ban_error is not None:
        raise _unavailable(ban_error, "ban_user", user_id=str(user_id))
    return _admin_user(updated, _final_status(admin, updated))

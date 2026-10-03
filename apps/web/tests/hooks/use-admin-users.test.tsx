/**
 * Contrat des hooks d'administration des utilisateurs (phase 3).
 * - `useAdminUsers()` : `useInfiniteQuery` sur GET /api/v1/admin/users?limit=50[&cursor=...].
 * - `useInviteUser()` : mutation POST /api/v1/admin/users/invite ; la variable est le corps tel quel
 *   `{ email, full_name, role }`.
 * - `useUpdateUser()` : mutation PATCH /api/v1/admin/users/{id} ; la variable est `{ id, body }`
 *   où `body` ne contient que les clés modifiées (`{ role }` ou `{ is_active }`).
 * - Les deux mutations invalident `queryKeys.adminUsers()` ET `queryKeys.adminAudit()`.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  type UpdateUserBody,
  useAdminUsers,
  useInviteUser,
  useUpdateUser,
} from "@/hooks/use-admin-users";
import { ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

import { adminUserFixture, adminUsersPage, apiErrorBody } from "../helpers/fixtures";
import { makeNoRetryClient, wrapperFor } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const BASE = "http://localhost:3000";
const USERS_URL = `${BASE}/api/v1/admin/users`;
const INVITE_URL = `${BASE}/api/v1/admin/users/invite`;
const USER_ID = "11111111-1111-4111-8111-111111111111";

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
  auth.signOut.mockResolvedValue({ error: null });
});

describe("queryKeys (phase 3)", () => {
  it("has the admin users and audit keys (LLD section 8)", () => {
    expect(queryKeys.adminUsers()).toEqual(["admin", "users"]);
    expect(queryKeys.adminAudit()).toEqual(["admin", "audit"]);
  });
});

describe("useAdminUsers", () => {
  it("requests the first page with limit=50 and no cursor", async () => {
    let url: URL | null = null;
    server.use(
      http.get(USERS_URL, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json(adminUsersPage([adminUserFixture()]));
      }),
    );
    const { result } = renderHook(() => useAdminUsers(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect((url as URL | null)?.searchParams.get("limit")).toBe("50");
    expect((url as URL | null)?.searchParams.has("cursor")).toBe(false);
    expect(result.current.data?.pages[0]?.items).toHaveLength(1);
  });

  it("follows next_cursor for the next page and stops when it is null", async () => {
    const cursors: (string | null)[] = [];
    server.use(
      http.get(USERS_URL, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        cursors.push(cursor);
        return cursor === null
          ? HttpResponse.json(adminUsersPage([adminUserFixture()], "cursor-1"))
          : HttpResponse.json(
              adminUsersPage([adminUserFixture({ id: "22222222-2222-4222-8222-222222222222" })]),
            );
      }),
    );
    const { result } = renderHook(() => useAdminUsers(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(true);

    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    expect(cursors).toEqual([null, "cursor-1"]);
    expect(result.current.hasNextPage).toBe(false);
  });

  it("exposes an API failure as an ApiError with its code and message", async () => {
    server.use(
      http.get(USERS_URL, () =>
        HttpResponse.json(apiErrorBody("FORBIDDEN", "No."), { status: 403 }),
      ),
    );
    const { result } = renderHook(() => useAdminUsers(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).code).toBe("FORBIDDEN");
    expect((result.current.error as ApiError).message).toBe("No.");
  });
});

describe("useInviteUser", () => {
  const body = { email: "new@example.test", full_name: "New Person", role: "marketer" } as const;

  it("POSTs exactly {email, full_name, role}", async () => {
    let received: unknown = null;
    server.use(
      http.post(INVITE_URL, async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(adminUserFixture({ status: "invited" }), { status: 201 });
      }),
    );
    const { result } = renderHook(() => useInviteUser(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await act(async () => {
      await result.current.mutateAsync(body);
    });
    expect(received).toEqual(body);
    expect(Object.keys(received as object).sort()).toEqual(["email", "full_name", "role"]);
  });

  it("invalidates the users list AND the audit log on success", async () => {
    server.use(
      http.post(INVITE_URL, () =>
        HttpResponse.json(adminUserFixture({ status: "invited" }), { status: 201 }),
      ),
    );
    const client = makeNoRetryClient();
    client.setQueryData(queryKeys.adminUsers(), { pages: [], pageParams: [] });
    client.setQueryData(queryKeys.adminAudit(), { pages: [], pageParams: [] });
    client.setQueryData(queryKeys.me(), { id: "x" });
    const { result } = renderHook(() => useInviteUser(), { wrapper: wrapperFor(client) });
    await act(async () => {
      await result.current.mutateAsync(body);
    });
    expect(client.getQueryState(queryKeys.adminUsers())?.isInvalidated).toBe(true);
    expect(client.getQueryState(queryKeys.adminAudit())?.isInvalidated).toBe(true);
    expect(client.getQueryState(queryKeys.me())?.isInvalidated).toBe(false);
  });

  it("surfaces a 409 as an ApiError with code and message, and invalidates nothing", async () => {
    server.use(
      http.post(INVITE_URL, () =>
        HttpResponse.json(
          apiErrorBody("EMAIL_ALREADY_REGISTERED", "A user with this email already exists."),
          { status: 409 },
        ),
      ),
    );
    const client = makeNoRetryClient();
    client.setQueryData(queryKeys.adminUsers(), { pages: [], pageParams: [] });
    const { result } = renderHook(() => useInviteUser(), { wrapper: wrapperFor(client) });
    let caught: unknown = null;
    await act(async () => {
      caught = await result.current.mutateAsync(body).catch((error: unknown) => error);
    });
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
    expect((caught as ApiError).code).toBe("EMAIL_ALREADY_REGISTERED");
    expect((caught as ApiError).message).toBe("A user with this email already exists.");
    expect(client.getQueryState(queryKeys.adminUsers())?.isInvalidated).toBe(false);
  });
});

describe("useUpdateUser", () => {
  const PATCH_URL = `${USERS_URL}/${USER_ID}`;

  const changed: [UpdateUserBody][] = [
    [{ role: "admin" }],
    [{ is_active: false }],
    [{ is_active: true }],
  ];

  it.each(changed)("PATCHes only the changed key %j", async (changes) => {
    let method = "";
    let received: unknown = null;
    server.use(
      http.patch(PATCH_URL, async ({ request }) => {
        method = request.method;
        received = await request.json();
        return HttpResponse.json(adminUserFixture());
      }),
    );
    const { result } = renderHook(() => useUpdateUser(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await act(async () => {
      await result.current.mutateAsync({ id: USER_ID, body: changes });
    });
    expect(method).toBe("PATCH");
    expect(received).toEqual(changes);
  });

  it("invalidates the users list AND the audit log on success", async () => {
    server.use(http.patch(PATCH_URL, () => HttpResponse.json(adminUserFixture())));
    const client = makeNoRetryClient();
    client.setQueryData(queryKeys.adminUsers(), { pages: [], pageParams: [] });
    client.setQueryData(queryKeys.adminAudit(), { pages: [], pageParams: [] });
    const { result } = renderHook(() => useUpdateUser(), { wrapper: wrapperFor(client) });
    await act(async () => {
      await result.current.mutateAsync({ id: USER_ID, body: { role: "admin" } });
    });
    expect(client.getQueryState(queryKeys.adminUsers())?.isInvalidated).toBe(true);
    expect(client.getQueryState(queryKeys.adminAudit())?.isInvalidated).toBe(true);
  });

  it("surfaces LAST_ADMIN as an ApiError carrying the API message", async () => {
    server.use(
      http.patch(PATCH_URL, () =>
        HttpResponse.json(
          apiErrorBody("LAST_ADMIN", "At least one active administrator is required."),
          { status: 409 },
        ),
      ),
    );
    const { result } = renderHook(() => useUpdateUser(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    let caught: unknown = null;
    await act(async () => {
      caught = await result.current
        .mutateAsync({ id: USER_ID, body: { role: "marketer" } })
        .catch((error: unknown) => error);
    });
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).code).toBe("LAST_ADMIN");
    expect((caught as ApiError).message).toBe("At least one active administrator is required.");
  });
});

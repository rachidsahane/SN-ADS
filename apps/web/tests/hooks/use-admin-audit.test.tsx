/** `useAdminAudit()` : `useInfiniteQuery` sur GET /api/v1/admin/audit-log?limit=50, toujours rafraîchi (staleTime 0). */
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAdminAudit } from "@/hooks/use-admin-audit";
import { ApiError } from "@/lib/api/client";

import { apiErrorBody, auditEntryFixture, auditPage } from "../helpers/fixtures";
import { makeNoRetryClient, makeQueryClient, wrapperFor } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const AUDIT_URL = "http://localhost:3000/api/v1/admin/audit-log";

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
  auth.signOut.mockResolvedValue({ error: null });
});

describe("useAdminAudit", () => {
  it("requests the first page with limit=50 and no cursor", async () => {
    let url: URL | null = null;
    server.use(
      http.get(AUDIT_URL, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json(auditPage([auditEntryFixture()]));
      }),
    );
    const { result } = renderHook(() => useAdminAudit(), {
      wrapper: wrapperFor(makeQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect((url as URL | null)?.searchParams.get("limit")).toBe("50");
    expect((url as URL | null)?.searchParams.has("cursor")).toBe(false);
  });

  it("follows next_cursor and stops when it is null", async () => {
    const cursors: (string | null)[] = [];
    server.use(
      http.get(AUDIT_URL, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        cursors.push(cursor);
        return HttpResponse.json(
          cursor === null
            ? auditPage([auditEntryFixture({ id: 2 })], "audit-cursor")
            : auditPage([auditEntryFixture({ id: 1 })]),
        );
      }),
    );
    const { result } = renderHook(() => useAdminAudit(), {
      wrapper: wrapperFor(makeQueryClient()),
    });
    await waitFor(() => expect(result.current.hasNextPage).toBe(true));
    await act(async () => {
      await result.current.fetchNextPage();
    });
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    expect(cursors).toEqual([null, "audit-cursor"]);
    expect(result.current.hasNextPage).toBe(false);
  });

  it("refetches on every mount (staleTime 0, even with a 30 s default in the cache)", async () => {
    let calls = 0;
    server.use(
      http.get(AUDIT_URL, () => {
        calls += 1;
        return HttpResponse.json(auditPage([auditEntryFixture()]));
      }),
    );
    const client = makeQueryClient();
    const first = renderHook(() => useAdminAudit(), { wrapper: wrapperFor(client) });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    first.unmount();
    const second = renderHook(() => useAdminAudit(), { wrapper: wrapperFor(client) });
    await waitFor(() => expect(calls).toBe(2));
    await waitFor(() => expect(second.result.current.isFetching).toBe(false));
  });

  it("exposes an API failure as an ApiError", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(apiErrorBody("FORBIDDEN", "No."), { status: 403 }),
      ),
    );
    const { result } = renderHook(() => useAdminAudit(), {
      wrapper: wrapperFor(makeNoRetryClient()),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).code).toBe("FORBIDDEN");
  });
});

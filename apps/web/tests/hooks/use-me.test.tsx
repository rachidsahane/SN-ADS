import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

import { apiErrorBody, meFixture } from "../helpers/fixtures";
import { makeQueryClient, wrapperFor } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const ME_URL = "http://localhost:3000/api/v1/me";

describe("queryKeys.me", () => {
  it("is ['me'] (LLD section 8)", () => {
    expect(queryKeys.me()).toEqual(["me"]);
  });
});

describe("useMe", () => {
  const assign = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
    vi.stubGlobal("location", {
      ...window.location,
      origin: "http://localhost:3000",
      pathname: "/predict",
      search: "",
      assign,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the profile from GET /api/v1/me", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture())));
    const client = makeQueryClient();
    const { result } = renderHook(() => useMe(), { wrapper: wrapperFor(client) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(meFixture());
    expect(client.getQueryData(queryKeys.me())).toEqual(meFixture());
  });

  it("is loading before the answer arrives", () => {
    server.use(http.get(ME_URL, () => new Promise(() => undefined)));
    const { result } = renderHook(() => useMe(), { wrapper: wrapperFor(makeQueryClient()) });
    expect(result.current.isPending).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("does not retry a failure (retry: false)", async () => {
    let calls = 0;
    server.use(
      http.get(ME_URL, () => {
        calls += 1;
        return HttpResponse.json(apiErrorBody("INTERNAL_ERROR"), { status: 500 });
      }),
    );
    const { result } = renderHook(() => useMe(), { wrapper: wrapperFor(makeQueryClient()) });
    await waitFor(() => expect(result.current.isError).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls).toBe(1);
    expect(result.current.error).toBeInstanceOf(ApiError);
  });

  it("lets apiFetch handle a 401: local sign-out, redirect to /login, error exposed", async () => {
    server.use(
      http.get(ME_URL, () => HttpResponse.json(apiErrorBody("TOKEN_EXPIRED"), { status: 401 })),
    );
    const { result } = renderHook(() => useMe(), { wrapper: wrapperFor(makeQueryClient()) });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(assign).toHaveBeenCalledWith("/login?next=%2Fpredict");
    expect((result.current.error as ApiError).code).toBe("TOKEN_EXPIRED");
  });

  it("does not call the API again within 30 seconds (staleTime) when remounted", async () => {
    let calls = 0;
    server.use(
      http.get(ME_URL, () => {
        calls += 1;
        return HttpResponse.json(meFixture());
      }),
    );
    const client = makeQueryClient();
    const first = renderHook(() => useMe(), { wrapper: wrapperFor(client) });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    first.unmount();
    const second = renderHook(() => useMe(), { wrapper: wrapperFor(client) });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });
});

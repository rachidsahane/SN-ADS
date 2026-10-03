import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, newRequestId } from "@/lib/api/client";

import { apiErrorBody } from "../helpers/fixtures";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const BASE = "http://localhost:3000";
/** Valeur factice construite à l'exécution (aucun jeton réel, aucun littéral en forme de jeton). */
const ACCESS = ["test", "only", "access"].join("-");

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
  auth.signOut.mockResolvedValue({ error: null });
});

describe("apiFetch", () => {
  it("returns the JSON body and sends an X-Request-ID header", async () => {
    let requestId: string | null = null;
    server.use(
      http.get(`${BASE}/api/health`, ({ request }) => {
        requestId = request.headers.get("X-Request-ID");
        return HttpResponse.json({ status: "ok", release: "r" });
      }),
    );
    await expect(apiFetch("/api/health")).resolves.toEqual({ status: "ok", release: "r" });
    expect(requestId).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("turns the standard error body into an ApiError", async () => {
    server.use(
      http.get(`${BASE}/api/v1/me`, () =>
        HttpResponse.json(
          { error: { code: "FORBIDDEN", message: "Nope.", details: [], request_id: "rid-1" } },
          { status: 403 },
        ),
      ),
    );
    await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "FORBIDDEN",
      requestId: "rid-1",
    });
  });

  it("falls back to INTERNAL_ERROR when the body is not the standard format", async () => {
    server.use(http.get(`${BASE}/api/x`, () => new HttpResponse("oops", { status: 500 })));
    const error = (await apiFetch("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("INTERNAL_ERROR");
  });

  it("sends a JSON body with a content type", async () => {
    let received: unknown = null;
    server.use(
      http.post(`${BASE}/api/v1/echo`, async ({ request }) => {
        received = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    await expect(
      apiFetch("/api/v1/echo", { method: "POST", body: { a: 1 } }),
    ).resolves.toBeUndefined();
    expect(received).toEqual({ a: 1 });
  });

  it("aborts the request when the timeout is reached", async () => {
    server.use(
      http.get(`${BASE}/api/slow`, async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );
    await expect(apiFetch("/api/slow", { timeoutMs: 30 })).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("aborts the request when the caller's signal is already aborted", async () => {
    server.use(http.get(`${BASE}/api/x`, () => HttpResponse.json({})));
    const controller = new AbortController();
    controller.abort();
    await expect(apiFetch("/api/x", { signal: controller.signal })).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});

describe("apiFetch: bearer token (phase 2)", () => {
  function captureAuthorization(path: string) {
    const seen: { value: string | null; called: boolean } = { value: null, called: false };
    server.use(
      http.get(`${BASE}${path}`, ({ request }) => {
        seen.value = request.headers.get("Authorization");
        seen.called = true;
        return HttpResponse.json({ ok: true });
      }),
    );
    return seen;
  }

  it("adds Authorization: Bearer <access_token> when a session exists", async () => {
    auth.getSession.mockResolvedValue({
      data: { session: { access_token: ACCESS } },
      error: null,
    });
    const seen = captureAuthorization("/api/v1/me");
    await apiFetch("/api/v1/me");
    expect(seen.value).toBe(`Bearer ${ACCESS}`);
  });

  it("sends no Authorization header without a session", async () => {
    const seen = captureAuthorization("/api/v1/me");
    await apiFetch("/api/v1/me");
    expect(seen.called).toBe(true);
    expect(seen.value).toBeNull();
  });

  it("still works (without a header) when reading the session fails", async () => {
    auth.getSession.mockRejectedValue(new Error("storage unavailable"));
    const seen = captureAuthorization("/api/v1/me");
    await apiFetch("/api/v1/me");
    expect(seen.called).toBe(true);
    expect(seen.value).toBeNull();
  });
});

describe("apiFetch: session errors (phase 2)", () => {
  const assign = vi.fn();

  beforeEach(() => {
    assign.mockReset();
    vi.stubGlobal("location", {
      ...window.location,
      origin: "http://localhost:3000",
      pathname: "/history/abc",
      search: "?x=1",
      assign,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["UNAUTHENTICATED", "TOKEN_EXPIRED"])(
    "a 401 %s signs out locally, goes to /login?next=<current page> and rethrows",
    async (code) => {
      server.use(
        http.get(`${BASE}/api/v1/me`, () => HttpResponse.json(apiErrorBody(code), { status: 401 })),
      );
      await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({
        name: "ApiError",
        status: 401,
        code,
      });
      expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
      expect(assign).toHaveBeenCalledTimes(1);
      expect(assign).toHaveBeenCalledWith(`/login?next=${encodeURIComponent("/history/abc?x=1")}`);
    },
  );

  it("a 403 ACCOUNT_DISABLED signs out locally and goes to /login?reason=disabled", async () => {
    server.use(
      http.get(`${BASE}/api/v1/me`, () =>
        HttpResponse.json(apiErrorBody("ACCOUNT_DISABLED"), { status: 403 }),
      ),
    );
    await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({
      status: 403,
      code: "ACCOUNT_DISABLED",
    });
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(assign).toHaveBeenCalledWith("/login?reason=disabled");
  });

  it("still redirects when the local sign-out itself fails", async () => {
    auth.signOut.mockRejectedValue(new Error("storage unavailable"));
    server.use(
      http.get(`${BASE}/api/v1/me`, () =>
        HttpResponse.json(apiErrorBody("TOKEN_EXPIRED"), { status: 401 }),
      ),
    );
    await expect(apiFetch("/api/v1/me")).rejects.toBeInstanceOf(ApiError);
    expect(assign).toHaveBeenCalledTimes(1);
  });

  it.each([
    [403, "FORBIDDEN"],
    [404, "NOT_FOUND"],
    [422, "VALIDATION_ERROR"],
    [500, "INTERNAL_ERROR"],
  ])("a %i %s neither signs out nor redirects", async (status, code) => {
    server.use(
      http.get(`${BASE}/api/v1/me`, () => HttpResponse.json(apiErrorBody(code), { status })),
    );
    await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({ status, code });
    expect(auth.signOut).not.toHaveBeenCalled();
    expect(assign).not.toHaveBeenCalled();
  });
});

describe("newRequestId", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns a UUID v4", () => {
    expect(newRequestId()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it("still returns a UUID v4 when crypto.randomUUID is unavailable (non-secure context)", () => {
    vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
    expect(newRequestId()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });
});

import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, newRequestId } from "@/lib/api/client";

import { server } from "../msw/server";

const BASE = "http://localhost:3000";

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

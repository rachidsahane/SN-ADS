// @vitest-environment node
import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const verifyOtp = vi.hoisted(() => vi.fn());
const reportError = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: async () => ({ auth: { verifyOtp } }),
}));
vi.mock("@/lib/observability", () => ({ reportError }));

import { GET } from "@/app/auth/confirm/route";

const TOKEN_HASH = "tokenhash-test-value-0001";

function call(query: Record<string, string>) {
  const url = new URL("http://localhost:3000/auth/confirm");
  for (const [key, value] of Object.entries(query)) {
    url.searchParams.set(key, value);
  }
  return GET(new NextRequest(url));
}

function target(response: Response): string {
  const location = response.headers.get("location");
  if (!location) {
    throw new Error("expected a redirect");
  }
  const url = new URL(location, "http://localhost:3000");
  return `${url.pathname}${url.search}`;
}

describe("GET /auth/confirm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    verifyOtp.mockResolvedValue({ data: { session: {}, user: {} }, error: null });
  });

  it.each(["invite", "recovery"])(
    "verifies a %s link and redirects to /auth/set-password",
    async (type) => {
      const response = await call({ token_hash: TOKEN_HASH, type, next: "/auth/set-password" });
      expect([302, 303, 307]).toContain(response.status);
      expect(target(response)).toBe("/auth/set-password");
      expect(verifyOtp).toHaveBeenCalledTimes(1);
      expect(verifyOtp).toHaveBeenCalledWith({ type, token_hash: TOKEN_HASH });
    },
  );

  it("follows a safe next path", async () => {
    const response = await call({ token_hash: TOKEN_HASH, type: "invite", next: "/history/abc" });
    expect(target(response)).toBe("/history/abc");
  });

  it.each(["//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)"])(
    "ignores the unsafe next=%s and goes to /predict",
    async (next) => {
      const response = await call({ token_hash: TOKEN_HASH, type: "invite", next });
      expect(target(response)).toBe("/predict");
    },
  );

  it("answers a redirect, not a 500, when next holds a character a Location header cannot carry", async () => {
    const response = await call({ token_hash: TOKEN_HASH, type: "invite", next: "/\u202e" });
    expect(response.status).toBe(302);
    expect(target(response)).toBe("/predict");
  });

  it("goes to /predict when next is absent", async () => {
    const response = await call({ token_hash: TOKEN_HASH, type: "recovery" });
    expect(target(response)).toBe("/predict");
  });

  it.each([
    ["signup", "signup"],
    ["magiclink", "magiclink"],
    ["email", "email"],
    ["empty", ""],
    ["upper case", "INVITE"],
  ])("refuses the type %s without calling Supabase", async (_name, type) => {
    const response = await call({ token_hash: TOKEN_HASH, type, next: "/auth/set-password" });
    expect(target(response)).toBe("/login?reason=invalid_link");
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it("refuses a missing type", async () => {
    const response = await call({ token_hash: TOKEN_HASH });
    expect(target(response)).toBe("/login?reason=invalid_link");
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it.each([
    ["missing", undefined],
    ["empty", ""],
  ])("refuses a %s token_hash without calling Supabase", async (_name, tokenHash) => {
    const query: Record<string, string> = { type: "invite" };
    if (tokenHash !== undefined) {
      query.token_hash = tokenHash;
    }
    const response = await call(query);
    expect(target(response)).toBe("/login?reason=invalid_link");
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it("redirects to the invalid-link login when the link was already used or expired", async () => {
    verifyOtp.mockResolvedValue({
      data: { session: null, user: null },
      error: { name: "AuthApiError", status: 403, code: "otp_expired", message: "expired" },
    });
    const response = await call({
      token_hash: TOKEN_HASH,
      type: "invite",
      next: "/auth/set-password",
    });
    expect(target(response)).toBe("/login?reason=invalid_link");
    expect(reportError).not.toHaveBeenCalled();
  });

  it("reports an unexpected exception and still redirects to the invalid-link login", async () => {
    verifyOtp.mockRejectedValue(new TypeError("fetch failed"));
    const response = await call({ token_hash: TOKEN_HASH, type: "invite" });
    expect(target(response)).toBe("/login?reason=invalid_link");
    expect(reportError).toHaveBeenCalledTimes(1);
    expect(reportError.mock.calls[0]?.[0]).toBeInstanceOf(Error);
  });

  it("never echoes the token in a redirect or in the error context", async () => {
    verifyOtp.mockRejectedValue(new TypeError("fetch failed"));
    const queries: Record<string, string>[] = [
      { token_hash: TOKEN_HASH, type: "invite", next: "/auth/set-password" },
      { token_hash: TOKEN_HASH, type: "bogus" },
    ];
    for (const query of queries) {
      const response = await call(query);
      expect(response.headers.get("location")).not.toContain(TOKEN_HASH);
    }
    verifyOtp.mockResolvedValue({ data: {}, error: null });
    const ok = await call({ token_hash: TOKEN_HASH, type: "recovery", next: "/auth/set-password" });
    expect(ok.headers.get("location")).not.toContain(TOKEN_HASH);
    expect(JSON.stringify(reportError.mock.calls)).not.toContain(TOKEN_HASH);
  });
});

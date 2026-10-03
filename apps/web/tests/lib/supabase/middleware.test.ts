// @vitest-environment node
import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClient = vi.hoisted(() => vi.fn());
const getUser = vi.hoisted(() => vi.fn());

vi.mock("@supabase/ssr", () => ({ createServerClient }));

import { isPublicPath, updateSession } from "@/lib/supabase/middleware";

type CookieAdapter = {
  getAll: () => { name: string; value: string }[];
  setAll: (items: { name: string; value: string; options?: Record<string, unknown> }[]) => void;
};

function capturedOptions() {
  return createServerClient.mock.calls[0]?.[2] as {
    cookies: CookieAdapter;
    cookieOptions: Record<string, unknown>;
  };
}

function request(path = "/predict", cookie?: string) {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: cookie ? { cookie } : {},
  });
}

describe("isPublicPath", () => {
  it.each([
    ["/login", true],
    ["/forgot-password", true],
    ["/auth/confirm", true],
    ["/auth/set-password", false],
    ["/", false],
    ["/predict", false],
    ["/admin/users", false],
    ["/auth", false],
    ["/login-evil", false],
    ["/loginx/anything", false],
  ])("%s -> %s", (path, expected) => {
    expect(isPublicPath(path)).toBe(expected);
  });
});

describe("updateSession", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    createServerClient.mockImplementation(() => ({ auth: { getUser } }));
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } }, error: null });
  });

  it("builds the client from the server-side Supabase URL, the anon key and the shared cookie name", async () => {
    await updateSession(request());
    expect(createServerClient.mock.calls[0]?.[0]).toBe("http://supabase.test");
    expect(createServerClient.mock.calls[0]?.[1]).toBe("test-only-anon");
    expect(capturedOptions().cookieOptions).toMatchObject({ name: "soronua-auth", path: "/" });
  });

  it("reads the session cookies of the incoming request", async () => {
    await updateSession(request("/predict", "soronua-auth=abc; other=1"));
    const names = capturedOptions()
      .cookies.getAll()
      .map((c) => c.name);
    expect(names).toContain("soronua-auth");
  });

  it("returns the user validated by the auth server (getUser, never getSession)", async () => {
    const result = await updateSession(request());
    expect(getUser).toHaveBeenCalledTimes(1);
    expect(result.user).toEqual({ id: "user-1" });
    expect(result.response).toBeInstanceOf(NextResponse);
  });

  it("returns no user when there is no session", async () => {
    getUser.mockResolvedValue({ data: { user: null }, error: null });
    expect((await updateSession(request())).user).toBeNull();
  });

  it("treats a getUser error as no user", async () => {
    getUser.mockResolvedValue({ data: { user: null }, error: { message: "invalid JWT" } });
    expect((await updateSession(request())).user).toBeNull();
  });

  it("treats an error result as no user even if a user object is present", async () => {
    getUser.mockResolvedValue({
      data: { user: { id: "user-1" } },
      error: { message: "bad" },
    });
    expect((await updateSession(request())).user).toBeNull();
  });

  it("treats a network failure as no user instead of crashing the request", async () => {
    getUser.mockRejectedValue(new TypeError("fetch failed"));
    expect((await updateSession(request())).user).toBeNull();
  });

  it("writes cookies refreshed by Supabase on the response and on the request", async () => {
    getUser.mockImplementation(async () => {
      capturedOptions().cookies.setAll([
        { name: "soronua-auth", value: "refreshed", options: { path: "/", maxAge: 3600 } },
      ]);
      return { data: { user: { id: "user-1" } }, error: null };
    });
    const incoming = request("/predict", "soronua-auth=old");
    const { response } = await updateSession(incoming);
    expect(response.cookies.get("soronua-auth")?.value).toBe("refreshed");
    expect(response.headers.get("set-cookie")).toContain("soronua-auth=refreshed");
    expect(incoming.cookies.get("soronua-auth")?.value).toBe("refreshed");
  });
});

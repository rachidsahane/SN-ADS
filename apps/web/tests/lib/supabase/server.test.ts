import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClient = vi.hoisted(() => vi.fn());
const cookieStore = vi.hoisted(() => ({ getAll: vi.fn(), set: vi.fn() }));
const cookies = vi.hoisted(() => vi.fn());

vi.mock("@supabase/ssr", () => ({ createServerClient }));
vi.mock("next/headers", () => ({ cookies }));

import { createSupabaseServerClient } from "@/lib/supabase/server";

type CookieAdapter = {
  getAll: () => unknown;
  setAll: (items: { name: string; value: string; options?: Record<string, unknown> }[]) => void;
};

function capturedOptions() {
  return createServerClient.mock.calls[0]?.[2] as {
    cookies: CookieAdapter;
    cookieOptions: Record<string, unknown>;
  };
}

describe("createSupabaseServerClient", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    cookies.mockResolvedValue(cookieStore);
    cookieStore.getAll.mockReturnValue([{ name: "soronua-auth", value: "stored" }]);
    createServerClient.mockReturnValue({ auth: {} });
  });

  it("targets the server-side Supabase base URL (NEXT_PUBLIC_SUPABASE_URL) with the public anon key", async () => {
    await createSupabaseServerClient();
    expect(createServerClient).toHaveBeenCalledTimes(1);
    expect(createServerClient.mock.calls[0]?.[0]).toBe("http://supabase.test");
    expect(createServerClient.mock.calls[0]?.[1]).toBe("test-only-anon");
  });

  it("awaits cookies() (Next 15: asynchronous) and reads them through getAll", async () => {
    await createSupabaseServerClient();
    expect(cookies).toHaveBeenCalledTimes(1);
    expect(capturedOptions().cookies.getAll()).toEqual([{ name: "soronua-auth", value: "stored" }]);
  });

  it("uses the same cookie name as the browser client", async () => {
    await createSupabaseServerClient();
    expect(capturedOptions().cookieOptions).toMatchObject({
      name: "soronua-auth",
      sameSite: "lax",
      path: "/",
    });
  });

  it("writes refreshed cookies to the store with their options", async () => {
    await createSupabaseServerClient();
    capturedOptions().cookies.setAll([
      { name: "soronua-auth", value: "fresh", options: { path: "/", maxAge: 60 } },
    ]);
    expect(cookieStore.set).toHaveBeenCalledWith("soronua-auth", "fresh", {
      path: "/",
      maxAge: 60,
    });
  });

  it("does not throw when cookies are read-only (Server Component render)", async () => {
    cookieStore.set.mockImplementation(() => {
      throw new Error("Cookies can only be modified in a Server Action or Route Handler");
    });
    await createSupabaseServerClient();
    expect(() =>
      capturedOptions().cookies.setAll([{ name: "soronua-auth", value: "fresh" }]),
    ).not.toThrow();
  });

  it("returns the client built by @supabase/ssr", async () => {
    const client = { auth: { marker: true } };
    createServerClient.mockReturnValue(client);
    await expect(createSupabaseServerClient()).resolves.toBe(client);
  });
});

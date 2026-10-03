import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createBrowserClient = vi.hoisted(() => vi.fn());
vi.mock("@supabase/ssr", () => ({ createBrowserClient }));

async function loadFresh() {
  vi.resetModules();
  return import("@/lib/supabase/browser");
}

describe("getBrowserSupabase", () => {
  beforeEach(() => {
    createBrowserClient.mockReset();
    createBrowserClient.mockImplementation(() => ({ auth: {} }));
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("talks to the page's own origin (AD-07: same-origin /auth/v1) with the public anon key", async () => {
    const { getBrowserSupabase } = await loadFresh();
    getBrowserSupabase();
    expect(createBrowserClient).toHaveBeenCalledTimes(1);
    const [url, key] = createBrowserClient.mock.calls[0] ?? [];
    expect(url).toBe(window.location.origin);
    expect(url).toBe("http://localhost:3000");
    expect(key).toBe("test-only-anon");
  });

  it("uses the shared cookie options (name soronua-auth, SameSite=Lax, path /)", async () => {
    const { getBrowserSupabase } = await loadFresh();
    getBrowserSupabase();
    const options = createBrowserClient.mock.calls[0]?.[2] as {
      cookieOptions: Record<string, unknown>;
    };
    expect(options.cookieOptions).toMatchObject({
      name: "soronua-auth",
      sameSite: "lax",
      path: "/",
    });
  });

  it("is a singleton: the client is created once", async () => {
    const { getBrowserSupabase } = await loadFresh();
    expect(getBrowserSupabase()).toBe(getBrowserSupabase());
    expect(createBrowserClient).toHaveBeenCalledTimes(1);
  });
});

describe("AUTH_COOKIE_OPTIONS (lib/supabase/shared.ts)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("has one fixed cookie name shared by browser, server and middleware (pitfall P1)", async () => {
    vi.resetModules();
    const { AUTH_COOKIE_OPTIONS } = await import("@/lib/supabase/shared");
    expect(AUTH_COOKIE_OPTIONS.name).toBe("soronua-auth");
    expect(AUTH_COOKIE_OPTIONS.sameSite).toBe("lax");
    expect(AUTH_COOKIE_OPTIONS.path).toBe("/");
  });

  it("is not Secure in the local environment only", async () => {
    vi.resetModules();
    const local = await import("@/lib/supabase/shared");
    expect(local.AUTH_COOKIE_OPTIONS.secure).toBe(false);

    for (const appEnv of ["staging", "production"]) {
      vi.resetModules();
      vi.stubEnv("NEXT_PUBLIC_APP_ENV", appEnv);
      const other = await import("@/lib/supabase/shared");
      expect(other.AUTH_COOKIE_OPTIONS.secure).toBe(true);
    }
  });
});

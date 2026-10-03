// @vitest-environment node
import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const updateSession = vi.hoisted(() => vi.fn());

// Seul `updateSession` est simulé : `isPublicPath` reste la vraie fonction (règle de routage réelle).
vi.mock("@/lib/supabase/middleware", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/supabase/middleware")>()),
  updateSession,
}));

import { config, middleware } from "@/middleware";

function request(path: string) {
  return new NextRequest(`http://localhost:3000${path}`);
}

function withSession(authenticated: boolean, refreshedCookie = false, disabled = false) {
  updateSession.mockImplementation(async () => {
    const response = NextResponse.next();
    if (refreshedCookie) {
      response.cookies.set("soronua-auth", "refreshed", { path: "/" });
    }
    return { response, user: authenticated ? { id: "user-1" } : null, disabled };
  });
}

function locationOf(response: Response): URL {
  const location = response.headers.get("location");
  if (!location) {
    throw new Error("expected a redirect");
  }
  return new URL(location);
}

describe("middleware: unauthenticated visitor", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    withSession(false);
  });

  it("redirects /predict to /login with the requested path in next (307)", async () => {
    const response = await middleware(request("/predict"));
    expect(response.status).toBe(307);
    const location = locationOf(response);
    expect(location.pathname).toBe("/login");
    expect(location.search).toBe("?next=%2Fpredict");
  });

  it("keeps the query string inside next", async () => {
    const location = locationOf(await middleware(request("/history/abc?x=1")));
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/history/abc?x=1");
  });

  it("redirects / to /login without a next parameter", async () => {
    const response = await middleware(request("/"));
    expect(response.status).toBe(307);
    const location = locationOf(response);
    expect(location.pathname).toBe("/login");
    expect(location.search).toBe("");
  });

  it("redirects /auth/set-password to /login?reason=invalid_link (the page needs the session of /auth/confirm)", async () => {
    const location = locationOf(await middleware(request("/auth/set-password")));
    expect(location.pathname).toBe("/login");
    expect(location.search).toBe("?reason=invalid_link");
  });

  it.each(["/login", "/forgot-password", "/auth/confirm"])(
    "lets the public path %s through without a session",
    async (path) => {
      const response = await middleware(request(path));
      expect(response.headers.get("location")).toBeNull();
      expect(response.status).toBe(200);
    },
  );

  it("keeps the query string of a public path untouched (auth/confirm?token_hash=...)", async () => {
    const response = await middleware(request("/auth/confirm?token_hash=abc&type=invite"));
    expect(response.headers.get("location")).toBeNull();
  });

  it("does not turn a lookalike path into a public path", async () => {
    const response = await middleware(request("/login-evil"));
    expect(response.status).toBe(307);
    expect(locationOf(response).pathname).toBe("/login");
  });
});

describe("middleware: deactivated account (phase 3)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it.each(["/predict", "/admin/users", "/admin/audit", "/"])(
    "redirects %s to /login?reason=disabled when the session belongs to a banned user",
    async (path) => {
      withSession(false, false, true);
      const response = await middleware(request(path));
      expect(response.status).toBe(307);
      const location = locationOf(response);
      expect(location.pathname).toBe("/login");
      expect(location.search).toBe("?reason=disabled");
    },
  );

  it("does not add a next parameter to the disabled redirect", async () => {
    withSession(false, false, true);
    const location = locationOf(await middleware(request("/predict?x=1")));
    expect(location.searchParams.has("next")).toBe(false);
  });

  it("copies the refreshed session cookies onto the disabled redirect", async () => {
    withSession(false, true, true);
    const response = await middleware(request("/predict"));
    expect(response.cookies.get("soronua-auth")?.value).toBe("refreshed");
  });

  it("lets /login itself through (no redirect loop)", async () => {
    withSession(false, false, true);
    const response = await middleware(request("/login?reason=disabled"));
    expect(response.headers.get("location")).toBeNull();
    expect(response.status).toBe(200);
  });

  it("keeps the usual /login?next=... redirect for a visitor who is not banned", async () => {
    withSession(false, false, false);
    const location = locationOf(await middleware(request("/admin/users")));
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/admin/users");
    expect(location.searchParams.has("reason")).toBe(false);
  });
});

describe("middleware: authenticated user", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    withSession(true);
  });

  it.each(["/", "/predict", "/auth/set-password", "/admin/users"])(
    "lets %s through",
    async (path) => {
      const response = await middleware(request(path));
      expect(response.headers.get("location")).toBeNull();
      expect(response.status).toBe(200);
    },
  );

  it("calls updateSession with the incoming request exactly once", async () => {
    const incoming = request("/predict");
    await middleware(incoming);
    expect(updateSession).toHaveBeenCalledTimes(1);
    expect(updateSession).toHaveBeenCalledWith(incoming);
  });
});

describe("middleware: refreshed session cookies", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("keeps them on a pass-through response", async () => {
    withSession(true, true);
    const response = await middleware(request("/predict"));
    expect(response.cookies.get("soronua-auth")?.value).toBe("refreshed");
  });

  it("copies them onto the redirect to /login", async () => {
    withSession(false, true);
    const response = await middleware(request("/predict"));
    expect(response.status).toBe(307);
    expect(response.cookies.get("soronua-auth")?.value).toBe("refreshed");
  });

  it("copies them onto the invalid-link redirect", async () => {
    withSession(false, true);
    const response = await middleware(request("/auth/set-password"));
    expect(response.cookies.get("soronua-auth")?.value).toBe("refreshed");
  });
});

describe("middleware config.matcher (pitfall P7: middleware runs before rewrites)", () => {
  const source = config.matcher[0] as string;
  const matches = (path: string) => new RegExp(`^${source}$`).test(path);

  it("has a single matcher", () => {
    expect(config.matcher).toHaveLength(1);
  });

  it.each([
    "/",
    "/predict",
    "/login",
    "/forgot-password",
    "/auth/confirm",
    "/auth/set-password",
    "/admin/users",
  ])("runs on the page %s", (path) => {
    expect(matches(path)).toBe(true);
  });

  it.each([
    "/api/v1/me",
    "/api/health",
    "/auth/v1/token",
    "/auth/v1/verify",
    "/auth-templates/invite.html",
    "/_next/static/chunks/main.js",
    "/_next/image",
    "/healthz",
    "/icon.svg",
    "/favicon.ico",
  ])("does not run on %s", (path) => {
    expect(matches(path)).toBe(false);
  });
});

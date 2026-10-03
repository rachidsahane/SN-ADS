// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

type Rewrite = { source: string; destination: string };

async function rewritesWith(env: Record<string, string | undefined>): Promise<Rewrite[]> {
  vi.resetModules();
  for (const [name, value] of Object.entries(env)) {
    if (value === undefined) {
      vi.stubEnv(name, "");
    } else {
      vi.stubEnv(name, value);
    }
  }
  const { default: config } = await import("../next.config");
  const rewrites = await config.rewrites?.();
  return (Array.isArray(rewrites) ? rewrites : []) as Rewrite[];
}

describe("next.config rewrites (local same-origin proxy, D-026 and D-069)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("proxies /auth/v1/* to AUTH_PROXY_TARGET so the browser only talks to its own origin", async () => {
    const rewrites = await rewritesWith({
      API_PROXY_TARGET: "http://api.test:8000",
      AUTH_PROXY_TARGET: "http://kong.test:8000",
    });
    expect(rewrites).toContainEqual({
      source: "/auth/v1/:path*",
      destination: "http://kong.test:8000/auth/v1/:path*",
    });
  });

  it("keeps proxying /api/* to API_PROXY_TARGET", async () => {
    const rewrites = await rewritesWith({
      API_PROXY_TARGET: "http://api.test:8000",
      AUTH_PROXY_TARGET: "http://kong.test:8000",
    });
    expect(rewrites).toContainEqual({
      source: "/api/:path*",
      destination: "http://api.test:8000/api/:path*",
    });
  });

  it("adds no auth rewrite when AUTH_PROXY_TARGET is not set (on AWS the load balancer routes /auth/v1/*)", async () => {
    const rewrites = await rewritesWith({
      API_PROXY_TARGET: "http://api.test:8000",
      AUTH_PROXY_TARGET: undefined,
    });
    expect(rewrites.some((rewrite) => rewrite.source.startsWith("/auth/v1"))).toBe(false);
  });

  it("never rewrites the pages of the application (/auth/confirm, /auth/set-password)", async () => {
    const rewrites = await rewritesWith({ AUTH_PROXY_TARGET: "http://kong.test:8000" });
    for (const rewrite of rewrites) {
      expect(rewrite.source).not.toMatch(/^\/auth\/(confirm|set-password)/);
      expect(rewrite.source).not.toBe("/auth/:path*");
    }
  });
});

import { describe, expect, it } from "vitest";

import { EnvError, parsePublicEnv } from "@/lib/env";

const valid = {
  NEXT_PUBLIC_APP_ENV: "local",
  NEXT_PUBLIC_APP_RELEASE: "abc1234",
  NEXT_PUBLIC_SUPABASE_URL: "http://supabase.test",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "test-only-anon",
};

function messageOf(attempt: () => unknown): string {
  try {
    attempt();
  } catch (error) {
    return (error as Error).message;
  }
  throw new Error("expected the call to throw");
}

describe("parsePublicEnv", () => {
  it("accepts the minimal valid environment", () => {
    const parsed = parsePublicEnv(valid);
    expect(parsed.NEXT_PUBLIC_APP_ENV).toBe("local");
    expect(parsed.NEXT_PUBLIC_SUPABASE_URL).toBe("http://supabase.test");
    expect(parsed.NEXT_PUBLIC_SUPABASE_ANON_KEY).toBe("test-only-anon");
  });

  it("treats an empty Sentry DSN as absent (still optional before phase 16)", () => {
    const parsed = parsePublicEnv({ ...valid, NEXT_PUBLIC_SENTRY_DSN: "" });
    expect(parsed.NEXT_PUBLIC_SENTRY_DSN).toBeUndefined();
  });

  it("lists the invalid variable names without leaking their values", () => {
    const attempt = () => parsePublicEnv({ NEXT_PUBLIC_APP_ENV: "prod-secret-value" });
    expect(attempt).toThrow(EnvError);
    const message = messageOf(attempt);
    expect(message).toContain("NEXT_PUBLIC_APP_ENV");
    expect(message).toContain("NEXT_PUBLIC_APP_RELEASE");
    expect(message).not.toContain("prod-secret-value");
  });

  it("requires the Supabase URL and the public anon key (phase 2)", () => {
    const attempt = () =>
      parsePublicEnv({ NEXT_PUBLIC_APP_ENV: "local", NEXT_PUBLIC_APP_RELEASE: "abc1234" });
    expect(attempt).toThrow(EnvError);
    const message = messageOf(attempt);
    expect(message).toContain("NEXT_PUBLIC_SUPABASE_URL");
    expect(message).toContain("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  });

  it("treats empty Supabase variables as missing, hence invalid", () => {
    const message = messageOf(() =>
      parsePublicEnv({
        ...valid,
        NEXT_PUBLIC_SUPABASE_URL: " ",
        NEXT_PUBLIC_SUPABASE_ANON_KEY: "",
      }),
    );
    expect(message).toContain("NEXT_PUBLIC_SUPABASE_URL");
    expect(message).toContain("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  });

  it("rejects a Supabase URL that is not a URL, without echoing it", () => {
    const attempt = () =>
      parsePublicEnv({ ...valid, NEXT_PUBLIC_SUPABASE_URL: "not a url, really" });
    expect(attempt).toThrow(EnvError);
    const message = messageOf(attempt);
    expect(message).toContain("NEXT_PUBLIC_SUPABASE_URL");
    expect(message).not.toContain("really");
  });
});

import { describe, expect, it } from "vitest";

import { EnvError, parsePublicEnv } from "@/lib/env";

const valid = { NEXT_PUBLIC_APP_ENV: "local", NEXT_PUBLIC_APP_RELEASE: "abc1234" };

describe("parsePublicEnv", () => {
  it("accepts the minimal valid environment", () => {
    expect(parsePublicEnv(valid).NEXT_PUBLIC_APP_ENV).toBe("local");
  });

  it("treats empty optional variables as absent", () => {
    const parsed = parsePublicEnv({
      ...valid,
      NEXT_PUBLIC_SENTRY_DSN: "",
      NEXT_PUBLIC_SUPABASE_URL: " ",
    });
    expect(parsed.NEXT_PUBLIC_SENTRY_DSN).toBeUndefined();
    expect(parsed.NEXT_PUBLIC_SUPABASE_URL).toBeUndefined();
  });

  it("lists the invalid variable names without leaking their values", () => {
    const attempt = () => parsePublicEnv({ NEXT_PUBLIC_APP_ENV: "prod-secret-value" });
    expect(attempt).toThrow(EnvError);
    try {
      attempt();
    } catch (error) {
      const message = (error as Error).message;
      expect(message).toContain("NEXT_PUBLIC_APP_ENV");
      expect(message).toContain("NEXT_PUBLIC_APP_RELEASE");
      expect(message).not.toContain("prod-secret-value");
    }
  });
});

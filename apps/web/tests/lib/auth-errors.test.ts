import { describe, expect, it } from "vitest";

import { classifyAuthError } from "@/lib/auth-errors";

describe("classifyAuthError", () => {
  it.each([400, 403])("classifies the code user_banned as disabled (status %s)", (status) => {
    expect(classifyAuthError({ status, code: "user_banned" })).toBe("disabled");
  });

  it("lets disabled win over a 5xx-looking error that carries the user_banned code", () => {
    expect(classifyAuthError({ status: 500, code: "user_banned" })).toBe("disabled");
  });

  it("classifies by code, never by status alone (a bare 403 stays rejected)", () => {
    expect(classifyAuthError({ status: 403, code: "bad_jwt" })).toBe("rejected");
  });

  it("keeps invalid_credentials as rejected", () => {
    expect(classifyAuthError({ status: 400, code: "invalid_credentials" })).toBe("rejected");
  });

  it("keeps 429 and over_* codes as rate_limited", () => {
    expect(classifyAuthError({ status: 429 })).toBe("rate_limited");
    expect(classifyAuthError({ status: 429, code: "over_request_rate_limit" })).toBe(
      "rate_limited",
    );
  });

  it("keeps a retryable fetch error as unavailable", () => {
    expect(classifyAuthError({ name: "AuthRetryableFetchError", status: 0 })).toBe("unavailable");
  });

  it("keeps a 5xx without the banned code as unavailable", () => {
    expect(classifyAuthError({ status: 502 })).toBe("unavailable");
  });
});

import { describe, expect, it, vi } from "vitest";

import { reportError } from "@/lib/observability";

function captureLog(run: () => void): Record<string, unknown> {
  const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  run();
  expect(spy).toHaveBeenCalledOnce();
  return JSON.parse(String(spy.mock.calls[0]?.[0])) as Record<string, unknown>;
}

describe("reportError", () => {
  it("logs one JSON line with service, release, error and context", () => {
    const line = captureLog(() => reportError(new Error("boom"), { requestId: "r-1", page: "/x" }));
    expect(line).toMatchObject({
      level: "error",
      service: "web",
      environment: "local",
      release: "test",
      error: { name: "Error", message: "boom" },
      requestId: "r-1",
      page: "/x",
    });
  });

  it("redacts sensitive context keys such as email or token", () => {
    const line = captureLog(() =>
      reportError(new Error("x"), { email: "a@b.c", accessToken: "t" }),
    );
    expect(line.email).toBe("[redacted]");
    expect(line.accessToken).toBe("[redacted]");
  });

  it("wraps non-Error values", () => {
    const line = captureLog(() => reportError("plain failure"));
    expect(line.error).toMatchObject({ message: "plain failure" });
  });
});

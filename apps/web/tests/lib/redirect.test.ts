import { describe, expect, it } from "vitest";

import { safeNextPath } from "@/lib/redirect";

describe("safeNextPath (SECURITY_NOTES 4.4, SEC-17)", () => {
  it.each(["/predict", "/history/abc?x=1", "/auth/set-password", "/admin/users#top", "/"])(
    "accepts the same-site path %s",
    (path) => {
      expect(safeNextPath(path)).toBe(path);
    },
  );

  it.each([
    ["protocol-relative URL", "//evil.com"],
    ["protocol-relative URL with a path", "//evil.com/predict"],
    ["slash then backslash", "/\\evil.com"],
    ["backslash inside the path", "/foo\\bar"],
    ["absolute https URL", "https://evil.com"],
    ["absolute http URL", "http://evil.com/predict"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,hi"],
    ["no leading slash", "predict"],
    ["leading space", " /predict"],
    ["tab hidden in the path (browsers strip it, giving //evil.com)", "/\t/evil.com"],
    ["newline hidden in the path", "/\n/evil.com"],
    ["carriage return hidden in the path", "/\r/evil.com"],
    ["NUL character", "/\u0000/evil.com"],
    ["empty string", ""],
  ])("falls back to /predict for %s", (_name, value) => {
    expect(safeNextPath(value)).toBe("/predict");
  });

  it("falls back for null and undefined", () => {
    expect(safeNextPath(null)).toBe("/predict");
    expect(safeNextPath(undefined)).toBe("/predict");
  });

  it("honours a custom fallback", () => {
    expect(safeNextPath("//evil.com", "/")).toBe("/");
    expect(safeNextPath(null, "/login")).toBe("/login");
    expect(safeNextPath("/ok", "/login")).toBe("/ok");
  });
});

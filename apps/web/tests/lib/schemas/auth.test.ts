import { describe, expect, it } from "vitest";

import { forgotPasswordSchema, loginSchema, setPasswordSchema } from "@/lib/schemas/auth";
import { labels } from "@/lib/labels";

/** Valeurs factices construites à l'exécution : jamais un mot de passe réel dans le dépôt. */
const filler = (length: number) => "x".repeat(length);

function issues(result: {
  success: boolean;
  error?: { issues: { path: PropertyKey[]; message: string }[] };
}) {
  return (result.error?.issues ?? []).map((issue) => [issue.path.join("."), issue.message]);
}

describe("loginSchema", () => {
  it("accepts a valid e-mail and any non-empty password (no length rule on sign-in)", () => {
    expect(loginSchema.safeParse({ email: "a@b.test", password: "short" }).success).toBe(true);
  });

  it("asks for the e-mail when it is empty", () => {
    expect(issues(loginSchema.safeParse({ email: "", password: "x" }))).toContainEqual([
      "email",
      labels.auth.emailRequired,
    ]);
  });

  it("asks for a valid e-mail", () => {
    expect(issues(loginSchema.safeParse({ email: "not-an-email", password: "x" }))).toContainEqual([
      "email",
      labels.auth.emailInvalid,
    ]);
  });

  it("refuses an e-mail longer than 254 characters", () => {
    const tooLong = `${filler(250)}@b.test`;
    expect(loginSchema.safeParse({ email: tooLong, password: "x" }).success).toBe(false);
  });

  it("asks for the password when it is empty", () => {
    expect(issues(loginSchema.safeParse({ email: "a@b.test", password: "" }))).toContainEqual([
      "password",
      labels.auth.passwordRequired,
    ]);
  });

  it("reports both fields at once", () => {
    const found = issues(loginSchema.safeParse({ email: "", password: "" }));
    expect(found).toContainEqual(["email", labels.auth.emailRequired]);
    expect(found).toContainEqual(["password", labels.auth.passwordRequired]);
  });
});

describe("forgotPasswordSchema", () => {
  it("accepts a valid e-mail", () => {
    expect(forgotPasswordSchema.safeParse({ email: "a@b.test" }).success).toBe(true);
  });

  it("uses the same e-mail messages as the sign-in form", () => {
    expect(issues(forgotPasswordSchema.safeParse({ email: "" }))).toContainEqual([
      "email",
      labels.auth.emailRequired,
    ]);
    expect(issues(forgotPasswordSchema.safeParse({ email: "nope" }))).toContainEqual([
      "email",
      labels.auth.emailInvalid,
    ]);
  });
});

describe("setPasswordSchema", () => {
  const pair = (length: number) => ({
    password: filler(length),
    confirmation: filler(length),
  });

  it("refuses 9 characters with the PRD message (US-01)", () => {
    expect(issues(setPasswordSchema.safeParse(pair(9)))).toContainEqual([
      "password",
      "Password must be at least 10 characters.",
    ]);
  });

  it("refuses an empty password with the same message", () => {
    expect(issues(setPasswordSchema.safeParse(pair(0)))).toContainEqual([
      "password",
      labels.auth.setPassword.tooShort,
    ]);
  });

  it("accepts 10 and 72 characters", () => {
    expect(setPasswordSchema.safeParse(pair(10)).success).toBe(true);
    expect(setPasswordSchema.safeParse(pair(72)).success).toBe(true);
  });

  it("refuses 73 characters", () => {
    expect(issues(setPasswordSchema.safeParse(pair(73)))).toContainEqual([
      "password",
      labels.auth.setPassword.tooLong,
    ]);
  });

  it("counts the 72-limit of the authentication service in bytes, not characters", () => {
    // gotrue (bcrypt) refuses more than 72 BYTES: 40 two-byte characters pass a character count but not the service.
    const accented = "é".repeat(40);
    expect(
      issues(setPasswordSchema.safeParse({ password: accented, confirmation: accented })),
    ).toEqual([["password", labels.auth.setPassword.tooLong]]);
    const fits = "é".repeat(36);
    expect(setPasswordSchema.safeParse({ password: fits, confirmation: fits }).success).toBe(true);
  });

  it("flags a confirmation that differs, on the confirmation field", () => {
    const result = setPasswordSchema.safeParse({
      password: filler(12),
      confirmation: filler(11),
    });
    expect(issues(result)).toContainEqual(["confirmation", labels.auth.setPassword.mismatch]);
  });

  it("does not report a mismatch when the two values are equal", () => {
    expect(issues(setPasswordSchema.safeParse(pair(12)))).toEqual([]);
  });
});

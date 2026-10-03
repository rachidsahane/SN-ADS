import { describe, expect, it } from "vitest";

import { labels } from "@/lib/labels";
import { inviteSchema } from "@/lib/schemas/admin";

const valid = { email: "ada@example.test", fullName: "Ada Lovelace", role: "marketer" };

function issues(input: unknown) {
  const result = inviteSchema.safeParse(input);
  return result.success
    ? []
    : result.error.issues.map((issue) => [issue.path.join("."), issue.message]);
}

describe("inviteSchema", () => {
  it("accepts a valid invitation", () => {
    expect(inviteSchema.safeParse(valid).success).toBe(true);
  });

  it("accepts both roles", () => {
    expect(inviteSchema.safeParse({ ...valid, role: "admin" }).success).toBe(true);
    expect(inviteSchema.safeParse({ ...valid, role: "marketer" }).success).toBe(true);
  });

  it("asks for the e-mail when it is empty or blank", () => {
    expect(issues({ ...valid, email: "" })).toContainEqual([
      "email",
      labels.admin.invite.emailRequired,
    ]);
    expect(issues({ ...valid, email: "   " })).toContainEqual([
      "email",
      labels.admin.invite.emailRequired,
    ]);
  });

  it("asks for a valid e-mail", () => {
    expect(issues({ ...valid, email: "not-an-email" })).toContainEqual([
      "email",
      labels.admin.invite.emailInvalid,
    ]);
  });

  it("accepts 254 characters and refuses 255 with the too-long message", () => {
    const at254 = `${"a".repeat(247)}@b.test`;
    const at255 = `${"a".repeat(248)}@b.test`;
    expect(at254).toHaveLength(254);
    expect(at255).toHaveLength(255);
    expect(inviteSchema.safeParse({ ...valid, email: at254 }).success).toBe(true);
    expect(issues({ ...valid, email: at255 })).toContainEqual([
      "email",
      labels.admin.invite.emailTooLong,
    ]);
  });

  it("trims the e-mail and the name", () => {
    const result = inviteSchema.safeParse({
      ...valid,
      email: "  ada@example.test ",
      fullName: "  Ada Lovelace  ",
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe("ada@example.test");
      expect(result.data.fullName).toBe("Ada Lovelace");
    }
  });

  it("asks for the name when it is empty or only blanks", () => {
    expect(issues({ ...valid, fullName: "" })).toContainEqual([
      "fullName",
      labels.admin.invite.nameRequired,
    ]);
    expect(issues({ ...valid, fullName: "    " })).toContainEqual([
      "fullName",
      labels.admin.invite.nameRequired,
    ]);
  });

  it("accepts 120 characters and refuses 121 with the too-long message", () => {
    expect(inviteSchema.safeParse({ ...valid, fullName: "n".repeat(120) }).success).toBe(true);
    expect(issues({ ...valid, fullName: "n".repeat(121) })).toContainEqual([
      "fullName",
      labels.admin.invite.nameTooLong,
    ]);
  });

  it("refuses a role outside marketer and admin", () => {
    expect(inviteSchema.safeParse({ ...valid, role: "owner" }).success).toBe(false);
    expect(inviteSchema.safeParse({ ...valid, role: "" }).success).toBe(false);
  });
});

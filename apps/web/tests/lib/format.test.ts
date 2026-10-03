import { afterEach, describe, expect, it } from "vitest";

import { formatDateTime } from "@/lib/format";

const originalTz = process.env.TZ;

afterEach(() => {
  if (originalTz === undefined) {
    delete process.env.TZ;
  } else {
    process.env.TZ = originalTz;
  }
});

describe("formatDateTime", () => {
  it("formats an ISO timestamp with microseconds as 'YYYY-MM-DD HH:mm UTC'", () => {
    expect(formatDateTime("2026-10-03T14:05:00.123456+00:00")).toBe("2026-10-03 14:05 UTC");
  });

  it("accepts the Z suffix", () => {
    expect(formatDateTime("2026-10-03T14:05:00Z")).toBe("2026-10-03 14:05 UTC");
  });

  it("converts an input carrying an offset to UTC", () => {
    expect(formatDateTime("2026-10-03T14:05:00+02:00")).toBe("2026-10-03 12:05 UTC");
  });

  it("can change the calendar day when converting to UTC", () => {
    expect(formatDateTime("2026-10-04T01:30:00+02:00")).toBe("2026-10-03 23:30 UTC");
  });

  it("returns garbage unchanged", () => {
    expect(formatDateTime("not a date")).toBe("not a date");
    expect(formatDateTime("")).toBe("");
  });

  it.each(["Pacific/Kiritimati", "America/Los_Angeles", "Asia/Kolkata"])(
    "gives the same output whatever the process time zone (%s)",
    (zone) => {
      process.env.TZ = zone;
      expect(formatDateTime("2026-10-03T14:05:00+00:00")).toBe("2026-10-03 14:05 UTC");
    },
  );
});

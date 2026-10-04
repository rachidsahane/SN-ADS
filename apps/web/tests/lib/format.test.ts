import { afterEach, describe, expect, it } from "vitest";

import {
  formatContribution,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatPercent,
  formatShare,
  formatVisits,
} from "@/lib/format";

const originalTz = process.env.TZ;

afterEach(() => {
  if (originalTz === undefined) {
    delete process.env.TZ;
  } else {
    process.env.TZ = originalTz;
  }
});

describe("formatDateTime (prototype: 'Oct 4, 2026, 10:09', 24 h, browser time zone)", () => {
  it("formats an ISO timestamp with microseconds", () => {
    process.env.TZ = "UTC";
    expect(formatDateTime("2026-10-03T14:05:00.123456+00:00")).toBe("Oct 3, 2026, 14:05");
  });

  it("accepts the Z suffix and never shows 'UTC' or seconds", () => {
    process.env.TZ = "UTC";
    expect(formatDateTime("2026-10-03T09:05:59Z")).toBe("Oct 3, 2026, 09:05");
  });

  it("uses the 24-hour clock at midnight (no '24:05')", () => {
    process.env.TZ = "UTC";
    expect(formatDateTime("2026-10-03T00:05:00Z")).toBe("Oct 3, 2026, 00:05");
  });

  it.each([
    ["Asia/Kolkata", "Oct 3, 2026, 19:35"],
    ["America/Los_Angeles", "Oct 3, 2026, 07:05"],
    ["Africa/Douala", "Oct 3, 2026, 15:05"],
  ])("shows the time of the browser's own zone (%s)", (zone, expected) => {
    process.env.TZ = zone;
    expect(formatDateTime("2026-10-03T14:05:00+00:00")).toBe(expected);
  });

  it("returns garbage unchanged", () => {
    expect(formatDateTime("not a date")).toBe("not a date");
    expect(formatDateTime("")).toBe("");
  });
});

describe("number formatters", () => {
  it("formats rates, visits, money and counts like the prototype", () => {
    expect(formatPercent(0.1503)).toBe("15.03%");
    expect(formatVisits(23.54)).toBe("23.5");
    expect(formatMoney(1860.505)).toBe("$1,860.51");
    expect(formatMoney(65000, 0)).toBe("$65,000");
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatShare(0.1449)).toBe("14%");
  });

  it("formats a driver contribution with a real minus sign", () => {
    expect(formatContribution(0.0012, "rate")).toBe("+0.12 pp");
    expect(formatContribution(-0.003, "rate")).toBe("−0.30 pp");
    expect(formatContribution(-0.3, "count")).toBe("−0.30");
    expect(formatContribution(0, "count")).toBe("+0.00");
  });
});

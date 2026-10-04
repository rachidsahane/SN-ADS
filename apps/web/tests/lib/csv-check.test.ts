import { describe, expect, it } from "vitest";

import { checkCsv, parseCsv } from "@/lib/csv-check";

const HEADER =
  "CustomerID,Age,Gender,Income,CampaignChannel,CampaignType,AdSpend,ClickThroughRate,ConversionRate,WebsiteVisits,PagesPerVisit,TimeOnSite,SocialShares,EmailOpens,EmailClicks,PreviousPurchases,LoyaltyPoints,AdvertisingPlatform,AdvertisingTool,Conversion";
const row = (id: number, overrides: Record<number, string> = {}) =>
  [
    id,
    38,
    "Female",
    65000,
    "Email",
    "Conversion",
    5000,
    0.15,
    0.1,
    24,
    5.4,
    7.6,
    50,
    11,
    5,
    3,
    2200,
    "IsConfid",
    "ToolConfid",
    1,
  ]
    .map((value, index) => overrides[index] ?? String(value))
    .join(",");

describe("parseCsv", () => {
  it("reads quotes, commas and line breaks inside quotes, CRLF and a BOM", () => {
    expect(parseCsv('﻿a,b\r\n"x, y","line1\nline2"\r\n\r\n')).toEqual([
      ["a", "b"],
      ["x, y", "line1\nline2"],
    ]);
    expect(parseCsv('"say ""hi"""')).toEqual([['say "hi"']]);
  });
});

describe("checkCsv", () => {
  it("accepts a valid file", () => {
    const result = checkCsv(`${HEADER}\n${row(1)}\n${row(2)}\n`);
    expect(result).toEqual({ rows: 2, problems: [], total: 0 });
  });

  it("reports every missing column and stops there", () => {
    const result = checkCsv("CustomerID,Age\n1,38\n");
    expect(result.total).toBe(18);
    expect(result.problems[0]).toEqual({ row: 1, column: "Gender", message: "Column is missing." });
  });

  it("reports an unreadable file", () => {
    expect(checkCsv("").problems[0]?.message).toBe(
      "No header row with the expected columns was found.",
    );
    expect(checkCsv(`${HEADER}\n`).problems[0]).toEqual({
      row: 2,
      column: "—",
      message: "The file has no data rows.",
    });
  });

  it("numbers rows from the header (row 2 = first data row) and names the column", () => {
    const result = checkCsv(
      `${HEADER}\n${row(1)}\n${row(2, { 1: "17", 7: "4.2", 18: "=SUM(A1)" })}`,
    );
    expect(result.problems).toEqual([
      { row: 3, column: "Age", message: "Must be between 18 and 100." },
      {
        row: 3,
        column: "ClickThroughRate",
        message: "Must be a fraction between 0 and 1 (got 4.2).",
      },
      {
        row: 3,
        column: "AdvertisingTool",
        message: "Cell starts with “=”; formulas are not allowed.",
      },
    ]);
  });

  const COLUMN_INDEX = Object.fromEntries(HEADER.split(",").map((name, index) => [name, index]));

  it.each([
    ["Gender", "Female ", null],
    ["Gender", "F", "Unknown value “F”. Expected Male or Female."],
    [
      "CampaignChannel",
      "Radio",
      "Unknown value “Radio”. Expected Social Media, Email, PPC, SEO or Referral.",
    ],
    ["AdSpend", "0", "Must be greater than 0."],
    ["Age", "38.5", "Must be a whole number."],
    ["Age", "abc", "Must be a number."],
    ["Age", "", "Required."],
    ["CustomerID", "0", "Must be a whole number from 1."],
    ["Conversion", "2", "Unknown value “2”. Expected 0 or 1."],
    ["AdvertisingPlatform", "+1", "Cell starts with “+”; formulas are not allowed."],
    ["AdvertisingPlatform", "x".repeat(101), "Use at most 100 characters."],
  ])("%s = %j", (column, value, expected) => {
    const result = checkCsv(
      `${HEADER}\n${row(1, { [COLUMN_INDEX[column as string] as number]: value as string })}`,
    );
    if (expected === null) {
      expect(result.total).toBe(0);
    } else {
      expect(result.problems).toEqual([{ row: 2, column, message: expected }]);
    }
  });

  it("refuses a duplicate campaign number", () => {
    const result = checkCsv(`${HEADER}\n${row(1)}\n${row(1)}`);
    expect(result.problems).toEqual([
      { row: 3, column: "CustomerID", message: "Duplicate campaign number 1." },
    ]);
  });

  it("counts every problem but lists only the first 100", () => {
    const rows = Array.from({ length: 150 }, (_, index) => row(index + 1, { 1: "5" })).join("\n");
    const result = checkCsv(`${HEADER}\n${rows}`);
    expect(result.total).toBe(150);
    expect(result.problems).toHaveLength(100);
  });
});

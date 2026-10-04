import { describe, expect, it } from "vitest";

import { DEFAULT_FORM, formFromInput, parseForm } from "@/lib/predict-form";

describe("parseForm", () => {
  it("accepts the starting form and returns the campaign as numbers", () => {
    const parsed = parseForm(DEFAULT_FORM);
    expect(parsed.errors).toEqual({});
    expect(parsed.values).toMatchObject({
      campaign_channel: "Email",
      campaign_type: "Conversion",
      ad_spend: 5000,
      age: 38,
      gender: "Female",
      income: 65000,
      pages_per_visit: 5.4,
      email_clicks: 5,
    });
  });

  it("strips spaces and thousands separators", () => {
    const parsed = parseForm({ ...DEFAULT_FORM, income: " 65,000 ", ad_spend: "1,250.50" });
    expect(parsed.values).toMatchObject({ income: 65000, ad_spend: 1250.5 });
  });

  it.each([
    ["age", "", "Required."],
    ["age", "abc", "Enter a number."],
    ["age", "Infinity", "Enter a number."],
    ["age", "20.5", "Must be a whole number."],
    ["age", "17", "Age must be between 18 and 100."],
    ["age", "101", "Age must be between 18 and 100."],
    ["ad_spend", "0", "Ad spend must be greater than 0."],
    ["ad_spend", "-5", "Ad spend must be greater than 0."],
    ["ad_spend", "10000001", "Ad spend must be between 0 and 10,000,000."],
    ["income", "100000001", "Income must be between 0 and 100,000,000."],
    ["time_on_site", "1441", "Time on site must be between 0 and 1,440."],
    ["pages_per_visit", "-1", "Pages per visit must be between 0 and 1,000."],
  ])("reports %s = %j as %j", (field, value, message) => {
    const parsed = parseForm({ ...DEFAULT_FORM, [field]: value });
    expect(parsed.errors[field]).toBe(message);
    expect(parsed.values).toBeNull();
  });

  it("refuses a channel that is not in the list", () => {
    expect(parseForm({ ...DEFAULT_FORM, campaign_channel: "Radio" }).errors.campaign_channel).toBe(
      "Required.",
    );
  });

  it("flags, without refusing, a value outside what the model has seen", () => {
    const ranges = { ad_spend: { min: 100, max: 9000 }, age: { min: 18, max: 69 } };
    const parsed = parseForm({ ...DEFAULT_FORM, ad_spend: "12000" }, [], ranges);
    expect(parsed.values).not.toBeNull();
    expect([...parsed.outOfRange]).toEqual(["ad_spend"]);
    expect(parseForm(DEFAULT_FORM, [], ranges).outOfRange.size).toBe(0);
  });

  it("requires the optional fields the model uses, and only those", () => {
    expect(parseForm(DEFAULT_FORM, ["advertising_platform"]).errors).toEqual({
      advertising_platform: "Required.",
    });
    const ok = parseForm({ ...DEFAULT_FORM, advertising_platform: " IsConfid " }, [
      "advertising_platform",
    ]);
    expect(ok.values).toMatchObject({ advertising_platform: "IsConfid" });
    expect(parseForm({ ...DEFAULT_FORM, advertising_tool: "x" }).values).not.toHaveProperty(
      "advertising_tool",
    );
    expect(
      parseForm({ ...DEFAULT_FORM, advertising_tool: "x".repeat(101) }, ["advertising_tool"]).errors
        .advertising_tool,
    ).toBe("Use at most 100 characters.");
  });
});

describe("formFromInput", () => {
  it("turns a campaign into text fields and skips empty optional ones", () => {
    const form = formFromInput({ age: 52, gender: "Male", advertising_tool: null });
    expect(form).toEqual({ age: "52", gender: "Male" });
  });
});

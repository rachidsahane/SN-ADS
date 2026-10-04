import { describe, expect, it } from "vitest";

import { labels } from "@/lib/labels";
import { makePredictSchema, toRequestBody } from "@/lib/schemas/prediction";

const valid = {
  campaign_channel: "Email",
  campaign_type: "Conversion",
  ad_spend: 5000,
  age: 35,
  gender: "Female",
  income: 60000,
  previous_purchases: 2,
  loyalty_points: 1000,
  pages_per_visit: 5.5,
  time_on_site: 7.5,
  social_shares: 50,
  email_opens: 9,
  email_clicks: 4,
};

function messages(input: unknown, required: string[] = []) {
  const result = makePredictSchema(required).safeParse(input);
  return result.success
    ? []
    : result.error.issues.map((issue) => [issue.path.join("."), issue.message]);
}

describe("makePredictSchema", () => {
  it("accepts a valid campaign", () => {
    expect(messages(valid)).toEqual([]);
  });

  it("refuses values outside the API bounds, field by field", () => {
    const e = labels.predict.errors;
    expect(messages({ ...valid, ad_spend: 0 })).toEqual([["ad_spend", e.spend(10_000_000)]]);
    expect(messages({ ...valid, age: 17 })).toEqual([["age", e.between(18, 100)]]);
    expect(messages({ ...valid, age: 30.5 })).toEqual([["age", e.integer]]);
    expect(messages({ ...valid, time_on_site: 1441 })).toEqual([
      ["time_on_site", e.between(0, 1440)],
    ]);
  });

  it("treats an empty number (NaN) as missing", () => {
    expect(messages({ ...valid, income: Number.NaN })).toEqual([
      ["income", labels.predict.errors.number],
    ]);
  });

  it("requires the optional fields only when the model uses them", () => {
    expect(messages(valid, ["advertising_platform"])).toEqual([
      ["advertising_platform", labels.predict.errors.required],
    ]);
    expect(messages({ ...valid, advertising_platform: "Alpha" }, ["advertising_platform"])).toEqual(
      [],
    );
  });

  it("leaves empty optional fields out of the request", () => {
    const body = toRequestBody({
      ...valid,
      advertising_platform: "",
      advertising_tool: "T",
    } as never);
    expect(body).not.toHaveProperty("advertising_platform");
    expect(body).toHaveProperty("advertising_tool", "T");
  });
});

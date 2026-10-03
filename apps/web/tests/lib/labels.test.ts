import { describe, expect, it } from "vitest";

import { labels } from "@/lib/labels";

describe("labels", () => {
  it("matches the PRD glossary (section 8) exactly", () => {
    expect(labels.glossary).toEqual({
      campaignChannel: "Channel",
      campaignType: "Campaign type",
      adSpend: "Ad spend (USD)",
      age: "Age",
      gender: "Gender",
      income: "Income (USD / year)",
      previousPurchases: "Previous purchases",
      loyaltyPoints: "Loyalty points",
      pagesPerVisit: "Pages per visit",
      timeOnSite: "Time on site (minutes)",
      socialShares: "Social shares",
      emailOpens: "Email opens",
      emailClicks: "Email clicks",
      advertisingPlatform: "Advertising platform",
      advertisingTool: "Advertising tool",
      clickThroughRate: "Click-through rate",
      conversionRate: "Conversion rate",
      websiteVisits: "Website visits",
      estimatedLeads: "Estimated leads",
      estimatedCostPerResult: "Estimated cost per result",
      performanceLevel: "Performance level",
    });
  });

  it("formats the error reference line", () => {
    expect(labels.errors.reference("abc")).toBe("Reference: abc");
  });

  it("provides the database status labels (phase 1)", () => {
    expect(labels.status.database.checking).toBe("Database: checking…");
    expect(labels.status.database.unreachable).toBe("Database: unreachable");
    expect(labels.status.database.connected("20261003120000")).toBe(
      "Database: connected (schema 20261003120000)",
    );
  });
});

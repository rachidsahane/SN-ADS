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

  it("drops the provisional phase-1 database status labels (home page deleted in phase 2)", () => {
    expect(labels).not.toHaveProperty("status");
  });

  it("provides the authentication labels exactly as specified (PRD US-01, US-02, F-01, F-04, CL-14)", () => {
    expect(labels.auth).toEqual({
      signIn: {
        title: "Sign in",
        submit: "Sign in",
        submitting: "Signing in…",
        email: "Email",
        password: "Password",
        forgotLink: "Forgot password?",
        invalidCredentials: "Invalid email or password.",
      },
      forgot: {
        title: "Forgot password",
        intro: "Enter your email address and we will send you a link to set a new password.",
        submit: "Send reset link",
        submitting: "Sending…",
        sent: "If an account exists for this email, a link to set a new password has been sent.",
        backToSignIn: "Back to sign in",
      },
      setPassword: {
        title: "Set your password",
        password: "Password",
        confirmation: "Confirm password",
        submit: "Set password",
        submitting: "Saving…",
        tooShort: "Password must be at least 10 characters.",
        tooLong: "Password must be at most 72 characters.",
        mismatch: "Passwords do not match.",
        samePassword: "Choose a password you have not used before.",
      },
      invalidLink:
        "This link is invalid or has expired. Ask an administrator for a new invitation.",
      signOut: "Sign out",
      emailRequired: "Enter your email address.",
      emailInvalid: "Enter a valid email address.",
      passwordRequired: "Enter your password.",
      tooManyRequests: "Too many requests. Please wait a moment.",
    });
  });

  it("provides the Predict page title", () => {
    expect(labels.predict.title).toBe("Predict");
  });

  it("keeps the service-unavailable text used for network failures on sign-in", () => {
    expect(labels.errors.serviceUnavailable).toBe(
      "The service is temporarily unavailable. Please try again in a few minutes.",
    );
  });
});

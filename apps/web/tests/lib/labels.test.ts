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
        title: "Reset your password",
        submit: "Send reset link",
        submitting: "Sending…",
        sent: "If an account exists for this email, a reset link has been sent. It opens the “Set your password” screen.",
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
      invitationFootnote: "Accounts are created by invitation from an administrator.",
      signOut: "Sign out",
      emailRequired: "Enter your email address.",
      emailInvalid: "Enter a valid email address.",
      passwordRequired: "Enter your password.",
      tooManyRequests: "Too many requests. Please wait a moment.",
      accountDisabled: "Your account has been deactivated. Contact an administrator.",
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

  it("provides the role-based navigation labels (phase 3)", () => {
    expect(labels.nav).toEqual({
      label: "Main",
      predict: "Predict",
      model: "Model",
      history: "History",
      data: "Data",
      models: "Models",
      users: "Users",
      audit: "Audit log",
      adminGroup: "Admin",
    });
  });

  it("provides the demo labels of the Data, Models and Model pages", () => {
    expect(labels.data.tiles.seed.key).toBe("Starting dataset");
    expect(labels.data.tiles.agency.needed(250)).toBe("Rows · 250 needed for “Agency data only”");
    expect(labels.data.upload).toBe("Upload CSV");
    expect(labels.models.train).toBe("Train a new version");
    expect(labels.models.activate).toBe("Activate this version");
    expect(labels.models.status).toEqual({
      queued: "Queued",
      running: "Running",
      succeeded: "Succeeded",
      failed: "Failed",
    });
    expect(labels.reliability).toEqual({ low: "Low", moderate: "Moderate", good: "Good" });
    expect(labels.model.noActive).toBe(
      "No active model yet. An administrator must train and activate a model.",
    );
  });

  it("provides the no-access text shown after the admin guard redirect (PRD CL-08)", () => {
    expect(labels.errors.noAccess).toBe("You do not have access to this page.");
  });

  it("provides the Users page labels (PRD US-03, US-04)", () => {
    const users = labels.admin.users;
    expect(users.title).toBe("Users");
    expect(users.invite).toBe("Invite user");
    expect(users.empty).toBe("No users yet.");
    expect(users.columns).toEqual({
      name: "Name",
      email: "Email",
      role: "Role",
      status: "Status",
      actions: "Actions",
    });
    expect(users.roleLabels).toEqual({ marketer: "Marketer", admin: "Administrator" });
    expect(users.roles).toEqual({ marketer: "Marketer", admin: "Admin" });
    expect(users.status).toEqual({
      invited: "Invited",
      active: "Active",
      deactivated: "Deactivated",
    });
    expect(users.deactivate).toBe("Deactivate");
    expect(users.reactivate).toBe("Reactivate");
    expect(users.you).toBe("(you)");
    expect(users.selfHint).toBe("You cannot change your own account.");
    expect(users.loadMore).toBe("Load more");
    expect(users.loading).toBe("Loading…");
  });

  it("builds the parameterised Users page texts", () => {
    expect(labels.admin.users.roleFor("ada@example.test")).toBe("Role for ada@example.test");
    expect(labels.admin.users.invitedNotice("ada@example.test")).toBe(
      "Invitation sent to ada@example.test.",
    );
  });

  it("provides the invitation dialog labels (PRD US-03)", () => {
    expect(labels.admin.invite).toEqual({
      title: "Invite user",
      email: "Email",
      fullName: "Full name",
      role: "Role",
      submit: "Send invitation",
      submitting: "Sending…",
      cancel: "Cancel",
      emailRequired: "Enter an email address.",
      emailInvalid: "Enter a valid email address.",
      emailTooLong: "Email must be at most 254 characters.",
      nameRequired: "Enter a full name.",
      nameTooLong: "Full name must be at most 120 characters.",
    });
  });

  it("provides the Audit log labels with the five columns of PRD US-05", () => {
    const audit = labels.admin.audit;
    expect(audit.title).toBe("Audit log");
    expect(audit.subtitle).toBe("Sensitive actions, newest first. Read only.");
    expect(audit.empty).toBe("No audit entries yet.");
    expect(audit.system).toBe("System");
    expect(audit.loadMore).toBe("Load more");
    expect(audit.columns).toEqual({
      date: "Date",
      author: "Author",
      action: "Action",
      target: "Target",
      details: "Details",
    });
  });

  it("builds the audit detail sentences", () => {
    const audit = labels.admin.audit;
    expect(audit.model(3)).toBe("Model v3");
    expect(audit.replaced(1)).toBe("Replaced v1");
    expect(audit.rows(6412, 1588)).toBe("6,412 training rows · 1,588 test rows");
    expect(audit.scope("all")).toBe("Scope: all data");
    expect(audit.role("marketer")).toBe("Role: marketer");
    expect(audit.roleChange("marketer", "admin")).toBe("marketer → admin");
  });
});

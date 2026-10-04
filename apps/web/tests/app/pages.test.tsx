import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { labels } from "@/lib/labels";

import {
  adminMeFixture,
  adminUsersPage,
  auditPage as auditPageFixture,
  meFixture,
} from "../helpers/fixtures";
import { renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
const navigation = vi.hoisted(() => ({
  redirect: vi.fn(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/predict",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => navigation);
// The form has its own tests (prediction-results, schema); here only the page around it.
vi.mock("@/components/predict/predict-view", () => ({
  PredictView: () => (
    <>
      <h1>Predict</h1>
      <p>predict view</p>
    </>
  ),
}));

import AppLayout from "@/app/(app)/layout";
import HomePage from "@/app/(app)/page";
import * as auditPage from "@/app/(app)/admin/audit/page";
import * as usersPage from "@/app/(app)/admin/users/page";
import * as predictPage from "@/app/(app)/predict/page";
import * as forgotPage from "@/app/(public)/forgot-password/page";
import * as loginPage from "@/app/(public)/login/page";
import * as setPasswordPage from "@/app/auth/set-password/page";

beforeEach(() => {
  vi.clearAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
  auth.signOut.mockResolvedValue({ error: null });
  server.use(http.get("http://localhost:3000/api/v1/me", () => HttpResponse.json(meFixture())));
});

describe("page titles (metadata)", () => {
  it.each([
    ["Sign in", loginPage.metadata],
    ["Reset your password", forgotPage.metadata],
    ["Set your password", setPasswordPage.metadata],
    ["Predict", predictPage.metadata],
    ["Users", usersPage.metadata],
    ["Audit log", auditPage.metadata],
  ])("the tab title of %s is its label", (title, metadata) => {
    expect(metadata.title).toBe(title);
  });
});

describe("public pages", () => {
  it("/login has the Sign in heading, the form and the forgot-password link", () => {
    renderWithClient(<loginPage.default />);
    expect(screen.getByRole("heading", { level: 1, name: "Sign in" })).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Forgot password?" })).toBeTruthy();
  });

  it("/forgot-password has the Reset your password heading and its form", () => {
    renderWithClient(<forgotPage.default />);
    expect(screen.getByRole("heading", { level: 1, name: "Reset your password" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeTruthy();
  });

  it("/auth/set-password has the Set your password heading and its two fields", () => {
    renderWithClient(<setPasswordPage.default />);
    expect(screen.getByRole("heading", { level: 1, name: "Set your password" })).toBeTruthy();
    expect(screen.getByLabelText("Password")).toBeTruthy();
    expect(screen.getByLabelText("Confirm password")).toBeTruthy();
  });

  it("each public page has exactly one level-1 heading", () => {
    for (const Page of [loginPage.default, forgotPage.default, setPasswordPage.default]) {
      const { unmount } = renderWithClient(<Page />);
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      unmount();
    }
  });

  it("no public page shows the application header or a Sign out button", () => {
    for (const Page of [loginPage.default, forgotPage.default, setPasswordPage.default]) {
      const { unmount } = renderWithClient(<Page />);
      expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
      unmount();
    }
  });
});

describe("protected area", () => {
  it("/ redirects to /predict", () => {
    HomePage();
    expect(navigation.redirect).toHaveBeenCalledWith("/predict");
  });

  it("/predict has the title and the prediction view", async () => {
    const page = await predictPage.default({ searchParams: Promise.resolve({}) });
    render(page);
    expect(screen.getByRole("heading", { level: 1, name: labels.predict.title })).toBeTruthy();
    expect(screen.getByText("predict view")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("/predict announces the no-access message in a toast for ?notice=forbidden (PRD CL-08)", async () => {
    const page = await predictPage.default({
      searchParams: Promise.resolve({ notice: "forbidden" }),
    });
    renderWithClient(page);
    expect(screen.getByRole("heading", { level: 1, name: "Predict" })).toBeTruthy();
    expect((await screen.findByRole("status")).textContent).toBe(
      "You do not have access to this page.",
    );
  });

  it.each([["whatever"], ["Forbidden"], [""]])("/predict ignores ?notice=%s", async (notice) => {
    const page = await predictPage.default({ searchParams: Promise.resolve({ notice }) });
    renderWithClient(page);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("/predict ignores a repeated notice parameter (array value)", async () => {
    const page = await predictPage.default({
      searchParams: Promise.resolve({ notice: ["forbidden", "x"] as unknown as string }),
    });
    renderWithClient(page);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("/admin/users has the Users heading and the Invite user button", async () => {
    server.use(
      http.get("http://localhost:3000/api/v1/me", () => HttpResponse.json(adminMeFixture())),
      http.get("http://localhost:3000/api/v1/admin/users", () =>
        HttpResponse.json(adminUsersPage([])),
      ),
    );
    renderWithClient(<usersPage.default />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Users" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Invite user" })).toBeTruthy();
    expect(await screen.findByText("No users yet.")).toBeTruthy();
  });

  it("/admin/audit has the Audit log heading and its table or empty state", async () => {
    server.use(
      http.get("http://localhost:3000/api/v1/admin/audit-log", () =>
        HttpResponse.json(auditPageFixture([])),
      ),
      http.get("http://localhost:3000/api/v1/admin/model-versions", () =>
        HttpResponse.json({ items: [] }),
      ),
      http.get("http://localhost:3000/api/v1/admin/users", () =>
        HttpResponse.json(adminUsersPage([])),
      ),
    );
    renderWithClient(<auditPage.default />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Audit log" })).toBeTruthy();
    expect(await screen.findByText("No audit entries yet.")).toBeTruthy();
  });

  it("the layout shows the header (name, Sign out) around the page content", async () => {
    renderWithClient(
      <AppLayout>
        <p>page content</p>
      </AppLayout>,
    );
    expect(await screen.findByTestId("user-name")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
    const main = screen.getByRole("main");
    expect(main.textContent).toContain("page content");
    expect(main.contains(screen.getByRole("button", { name: "Sign out" }))).toBe(false);
  });
});

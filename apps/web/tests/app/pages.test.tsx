import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { labels } from "@/lib/labels";

import { meFixture } from "../helpers/fixtures";
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

import AppLayout from "@/app/(app)/layout";
import HomePage from "@/app/(app)/page";
import PredictPage from "@/app/(app)/predict/page";
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
    ["Forgot password", forgotPage.metadata],
    ["Set your password", setPasswordPage.metadata],
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

  it("/forgot-password has the Forgot password heading and its form", () => {
    renderWithClient(<forgotPage.default />);
    expect(screen.getByRole("heading", { level: 1, name: "Forgot password" })).toBeTruthy();
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

  it("/predict is the empty Predict page: a title and nothing else", () => {
    const { container } = renderWithClient(<PredictPage />);
    expect(screen.getByRole("heading", { level: 1, name: labels.predict.title })).toBeTruthy();
    expect(
      container.querySelectorAll("button, input, select, textarea, a, form, table"),
    ).toHaveLength(0);
    expect(container.textContent).toBe("Predict");
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

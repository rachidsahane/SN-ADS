import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppHeader } from "@/components/layout/app-header";
import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

import { apiErrorBody, meFixture } from "../helpers/fixtures";
import { makeQueryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
const assign = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/predict",
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/observability", () => ({ reportError: vi.fn() }));

const ME_URL = "http://localhost:3000/api/v1/me";
const ACCESS = ["test", "only", "access"].join("-");

describe("AppHeader", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal("location", { ...window.location, origin: "http://localhost:3000", assign });
    auth.getSession.mockResolvedValue({
      data: { session: { access_token: ACCESS } },
      error: null,
    });
    auth.signOut.mockResolvedValue({ error: null });
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture())));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the wordmark as a link to /", () => {
    renderWithClient(<AppHeader />);
    const link = screen.getByRole("link", { name: labels.app.wordmark });
    expect(link.getAttribute("href")).toBe("/");
  });

  it("contains the main navigation landmark between the wordmark and the user name (phase 3)", async () => {
    renderWithClient(<AppHeader />);
    const navigation = screen.getByRole("navigation", { name: "Main" });
    const wordmark = screen.getByRole("link", { name: labels.app.wordmark });
    const name = await screen.findByTestId("user-name");
    expect(
      wordmark.compareDocumentPosition(navigation) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      navigation.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows the admin links to an administrator and only Predict to a marketer", async () => {
    renderWithClient(<AppHeader />);
    await screen.findByTestId("user-name");
    expect(screen.queryByRole("link", { name: "Users" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Audit log" })).toBeNull();
    expect(screen.getByRole("link", { name: "Predict" })).toBeTruthy();
  });

  it("shows the user's name from /api/v1/me in data-testid=user-name", async () => {
    renderWithClient(<AppHeader />);
    const name = await screen.findByTestId("user-name");
    expect(name.textContent).toBe("E2E Marketer A");
  });

  it("calls /api/v1/me with the bearer token of the session", async () => {
    let authorization: string | null = null;
    server.use(
      http.get(ME_URL, ({ request }) => {
        authorization = request.headers.get("Authorization");
        return HttpResponse.json(meFixture());
      }),
    );
    renderWithClient(<AppHeader />);
    await screen.findByTestId("user-name");
    expect(authorization).toBe(`Bearer ${ACCESS}`);
  });

  it("never shows the e-mail address in the header", async () => {
    const { container } = renderWithClient(<AppHeader />);
    await screen.findByTestId("user-name");
    expect(container.textContent).not.toContain("@");
  });

  it("shows a neutral busy placeholder while the profile loads, and the Sign out button already", async () => {
    server.use(http.get(ME_URL, () => new Promise(() => undefined)));
    const { container } = renderWithClient(<AppHeader />);
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText("E2E Marketer A")).toBeNull();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });

  it("removes the placeholder once the name is known", async () => {
    const { container } = renderWithClient(<AppHeader />);
    await screen.findByTestId("user-name");
    expect(container.querySelector('[aria-busy="true"]')).toBeNull();
  });

  describe("Sign out", () => {
    it("signs out locally, clears the query cache and reloads on /login", async () => {
      const client = makeQueryClient();
      const clear = vi.spyOn(client, "clear");
      renderWithClient(<AppHeader />, client);
      await screen.findByTestId("user-name");

      await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));

      await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
      expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
      expect(clear).toHaveBeenCalledTimes(1);
    });

    it("still goes to /login when the sign-out call fails", async () => {
      auth.signOut.mockRejectedValue(new Error("network down"));
      renderWithClient(<AppHeader />);
      await screen.findByTestId("user-name");

      await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));

      await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
    });

    it("works before the profile has loaded", async () => {
      server.use(http.get(ME_URL, () => new Promise(() => undefined)));
      renderWithClient(<AppHeader />);
      await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));
      await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
    });
  });

  describe("when /api/v1/me fails", () => {
    beforeEach(() => {
      server.use(
        http.get(ME_URL, () => HttpResponse.json(apiErrorBody("INTERNAL_ERROR"), { status: 500 })),
      );
    });

    it("keeps the Sign out button and shows no name", async () => {
      renderWithClient(<AppHeader />);
      await waitFor(() => expect(reportError).toHaveBeenCalled());
      expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
      expect(screen.queryByTestId("user-name")).toBeNull();
    });

    it("reports the error once, without personal data", async () => {
      renderWithClient(<AppHeader />);
      await waitFor(() => expect(reportError).toHaveBeenCalledTimes(1));
      const [error, context] = vi.mocked(reportError).mock.calls[0] ?? [];
      expect(error).toBeInstanceOf(ApiError);
      expect(JSON.stringify(context ?? {})).not.toContain("@");
    });

    it("stops showing the busy placeholder", async () => {
      const { container } = renderWithClient(<AppHeader />);
      await waitFor(() => expect(reportError).toHaveBeenCalled());
      expect(container.querySelector('[aria-busy="true"]')).toBeNull();
    });
  });
});

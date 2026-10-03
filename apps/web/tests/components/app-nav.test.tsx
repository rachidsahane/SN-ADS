import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppNav } from "@/components/layout/app-nav";
import { queryKeys } from "@/lib/api/query-keys";

import { adminMeFixture, apiErrorBody, meFixture } from "../helpers/fixtures";
import { makeQueryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
const nav = vi.hoisted(() => ({ pathname: "/predict" }));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

const ME_URL = "http://localhost:3000/api/v1/me";

function hrefs() {
  return screen.getAllByRole("link").map((link) => [link.textContent, link.getAttribute("href")]);
}

describe("AppNav (role-based navigation, phase 3)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    nav.pathname = "/predict";
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
  });

  it("is a navigation landmark labelled Main", () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture())));
    renderWithClient(<AppNav />);
    expect(screen.getByRole("navigation", { name: "Main" })).toBeTruthy();
  });

  it("shows only the Predict link to a marketer", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture({ role: "marketer" }))));
    const { client } = renderWithClient(<AppNav />);
    await waitFor(() => expect(client.getQueryData(queryKeys.me())).toBeTruthy());
    expect(hrefs()).toEqual([["Predict", "/predict"]]);
    expect(screen.queryByRole("link", { name: "Users" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Audit log" })).toBeNull();
  });

  it("shows Predict, Users and Audit log with the right addresses to an administrator", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(adminMeFixture())));
    renderWithClient(<AppNav />);
    expect(await screen.findByRole("link", { name: "Users" })).toBeTruthy();
    expect(hrefs()).toEqual([
      ["Predict", "/predict"],
      ["Users", "/admin/users"],
      ["Audit log", "/admin/audit"],
    ]);
  });

  it("shows only the Predict link while the profile is loading (no admin flash)", () => {
    server.use(http.get(ME_URL, () => new Promise(() => undefined)));
    renderWithClient(<AppNav />);
    expect(hrefs()).toEqual([["Predict", "/predict"]]);
  });

  it("shows only the Predict link when /api/v1/me fails", async () => {
    server.use(
      http.get(ME_URL, () => HttpResponse.json(apiErrorBody("INTERNAL_ERROR"), { status: 500 })),
    );
    const { client } = renderWithClient(<AppNav />);
    await waitFor(() => expect(client.getQueryState(queryKeys.me())?.status).toBe("error"));
    expect(hrefs()).toEqual([["Predict", "/predict"]]);
  });

  it("marks the current page with aria-current=page", async () => {
    nav.pathname = "/admin/users";
    server.use(http.get(ME_URL, () => HttpResponse.json(adminMeFixture())));
    renderWithClient(<AppNav />);
    const users = await screen.findByRole("link", { name: "Users" });
    expect(users.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Predict" }).getAttribute("aria-current")).toBeNull();
    expect(screen.getByRole("link", { name: "Audit log" }).getAttribute("aria-current")).toBeNull();
  });

  it("marks Predict as current on /predict", async () => {
    nav.pathname = "/predict";
    server.use(http.get(ME_URL, () => HttpResponse.json(adminMeFixture())));
    renderWithClient(<AppNav />, makeQueryClient());
    const predict = screen.getByRole("link", { name: "Predict" });
    expect(predict.getAttribute("aria-current")).toBe("page");
    await screen.findByRole("link", { name: "Audit log" });
    expect(screen.getByRole("link", { name: "Users" }).getAttribute("aria-current")).toBeNull();
  });
});

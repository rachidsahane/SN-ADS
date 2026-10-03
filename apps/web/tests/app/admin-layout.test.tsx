import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AdminLayout from "@/app/(app)/admin/layout";
import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

import { adminMeFixture, apiErrorBody, meFixture } from "../helpers/fixtures";
import { renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  usePathname: () => "/admin/users",
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("@/lib/observability", () => ({ reportError: vi.fn() }));

const ME_URL = "http://localhost:3000/api/v1/me";
const assign = vi.fn();

function renderLayout() {
  return renderWithClient(
    <AdminLayout>
      <p>admin content</p>
    </AdminLayout>,
  );
}

describe("admin layout guard (phase 3, D-087)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
    vi.stubGlobal("location", {
      ...window.location,
      origin: "http://localhost:3000",
      pathname: "/admin/users",
      search: "",
      assign,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a busy placeholder and not the children while the profile loads", () => {
    server.use(http.get(ME_URL, () => new Promise(() => undefined)));
    const { container } = renderLayout();
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText("admin content")).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("renders the children for an administrator, without any redirect", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(adminMeFixture())));
    renderLayout();
    expect(await screen.findByText("admin content")).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("sends a marketer to /predict?notice=forbidden once and never renders the children", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture({ role: "marketer" }))));
    const { container } = renderLayout();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict?notice=forbidden"));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("admin content")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("does not show the children to a marketer even for a single frame (checked on every render)", async () => {
    server.use(http.get(ME_URL, () => HttpResponse.json(meFixture({ role: "marketer" }))));
    const seen: boolean[] = [];
    const observer = new MutationObserver(() => {
      seen.push(document.body.textContent?.includes("admin content") ?? false);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    renderLayout();
    await waitFor(() => expect(router.replace).toHaveBeenCalled());
    observer.disconnect();
    expect(seen).not.toContain(true);
  });

  it("shows the service-unavailable alert and reports the error when /api/v1/me answers 500", async () => {
    server.use(
      http.get(ME_URL, () =>
        HttpResponse.json(apiErrorBody("INTERNAL_ERROR", "Boom.", "rid-500"), { status: 500 }),
      ),
    );
    renderLayout();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(labels.errors.serviceUnavailable);
    expect(screen.queryByText("admin content")).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();
    await waitFor(() => expect(reportError).toHaveBeenCalled());
    const [error, context] = vi.mocked(reportError).mock.calls[0] ?? [];
    expect(error).toBeInstanceOf(ApiError);
    expect(context).toMatchObject({ requestId: "rid-500" });
  });

  it("leaves a 403 ACCOUNT_DISABLED to apiFetch: local sign-out, /login?reason=disabled, no extra alert or report", async () => {
    server.use(
      http.get(ME_URL, () => HttpResponse.json(apiErrorBody("ACCOUNT_DISABLED"), { status: 403 })),
    );
    renderLayout();
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login?reason=disabled"));
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(screen.queryByText("admin content")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(reportError).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("leaves a 401 TOKEN_EXPIRED to apiFetch (sign-in screen), without reporting it", async () => {
    server.use(
      http.get(ME_URL, () => HttpResponse.json(apiErrorBody("TOKEN_EXPIRED"), { status: 401 })),
    );
    renderLayout();
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login?next=%2Fadmin%2Fusers"));
    expect(screen.queryByText("admin content")).toBeNull();
    expect(reportError).not.toHaveBeenCalled();
  });
});

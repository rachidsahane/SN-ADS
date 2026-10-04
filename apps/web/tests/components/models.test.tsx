import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DataSummary } from "@/components/admin/data-summary";
import { ModelDetail } from "@/components/admin/model-detail";
import { ModelsTable } from "@/components/admin/models-table";

import { apiErrorBody, modelVersionFixture } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const BASE = "http://localhost:3000/api/v1/admin";
const VERSION = modelVersionFixture();

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("DataSummary", () => {
  it("shows the seed rows, the agency rows and the test rows", async () => {
    server.use(
      http.get(`${BASE}/dataset/summary`, () =>
        HttpResponse.json({ seed_rows: 8000, agency_rows: 0, holdout_rows: 1602 }),
      ),
    );
    renderWithClient(<DataSummary />, makeNoRetryClient());
    expect(await screen.findByText("Seed rows: 8,000")).toBeTruthy();
    expect(screen.getByText("Agency rows: 0")).toBeTruthy();
    expect(screen.getByText("Test rows: 1,602")).toBeTruthy();
  });
});

describe("ModelsTable", () => {
  it("lists the versions with their status and a link to the details", async () => {
    server.use(
      http.get(`${BASE}/model-versions`, () =>
        HttpResponse.json({
          items: [
            modelVersionFixture({ id: "a", version: 4, status: "running" }),
            modelVersionFixture({ id: "b", version: 3, is_active: true }),
          ],
        }),
      ),
    );
    renderWithClient(<ModelsTable />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("model-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("v4");
    expect(screen.getAllByTestId("model-status").map((cell) => cell.textContent)).toEqual([
      "Running",
      "Succeeded",
    ]);
    expect(rows[1]?.textContent).toContain("Active");
    expect(screen.getAllByRole("link", { name: "Details" })[0]?.getAttribute("href")).toBe(
      "/admin/models/a",
    );
  });

  it("trains a new version when the button is pressed", async () => {
    let body: unknown = null;
    server.use(
      http.get(`${BASE}/model-versions`, () => HttpResponse.json({ items: [] })),
      http.post(`${BASE}/model-versions`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(modelVersionFixture({ status: "queued" }), { status: 202 });
      }),
    );
    renderWithClient(<ModelsTable />, makeNoRetryClient());
    expect(await screen.findByText("No version yet. Train the first one.")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Train a new version" }));
    await waitFor(() => expect(body).toEqual({ data_scope: "all" }));
  });

  it("shows the message of the API when a training is already running", async () => {
    server.use(
      http.get(`${BASE}/model-versions`, () => HttpResponse.json({ items: [] })),
      http.post(`${BASE}/model-versions`, () =>
        HttpResponse.json(
          apiErrorBody("TRAINING_ALREADY_RUNNING", "A training run is already in progress."),
          { status: 409 },
        ),
      ),
    );
    renderWithClient(<ModelsTable />, makeNoRetryClient());
    await userEvent.click(await screen.findByRole("button", { name: "Train a new version" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "A training run is already in progress.",
    );
  });
});

describe("ModelDetail", () => {
  const url = `${BASE}/model-versions/${VERSION.id}`;

  it("shows the measures of each figure and lets the administrator activate a succeeded version", async () => {
    let activated = false;
    server.use(
      http.get(url, () => HttpResponse.json(VERSION)),
      http.post(`${url}/activate`, () => {
        activated = true;
        return HttpResponse.json({ ...VERSION, is_active: true });
      }),
    );
    renderWithClient(<ModelDetail id={VERSION.id} />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("metrics-row");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain("Click-through rate");
    expect(rows[0]?.textContent).toContain("-0.0342");
    expect(rows[2]?.textContent).toContain("12.4");
    expect(rows[0]?.textContent).toContain("Low");
    await userEvent.click(screen.getByRole("button", { name: "Activate this version" }));
    await waitFor(() => expect(activated).toBe(true));
  });

  it("has no activate button for an active, a running or a failed version", async () => {
    for (const changes of [{ is_active: true }, { status: "running" }, { status: "failed" }]) {
      server.use(http.get(url, () => HttpResponse.json({ ...VERSION, ...changes })));
      const { unmount } = renderWithClient(<ModelDetail id={VERSION.id} />, makeNoRetryClient());
      await screen.findByTestId("model-status");
      expect(screen.queryByRole("button", { name: "Activate this version" })).toBeNull();
      unmount();
    }
  });

  it("shows the reason of a failure", async () => {
    server.use(
      http.get(url, () =>
        HttpResponse.json({
          ...VERSION,
          status: "failed",
          metrics: null,
          error_message:
            "Not enough data: at least 200 training rows and 50 test rows are required.",
        }),
      ),
    );
    renderWithClient(<ModelDetail id={VERSION.id} />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Not enough data");
    expect(screen.queryAllByTestId("metrics-row")).toHaveLength(0);
  });

  it("polls every 3 seconds while the version is running", async () => {
    let calls = 0;
    server.use(
      http.get(url, () => {
        calls += 1;
        return HttpResponse.json({ ...VERSION, status: calls < 2 ? "running" : "succeeded" });
      }),
    );
    renderWithClient(<ModelDetail id={VERSION.id} />, makeNoRetryClient());
    expect(await screen.findByText("Running")).toBeTruthy();
    expect(await screen.findByText("Succeeded", {}, { timeout: 6000 })).toBeTruthy();
    expect(calls).toBeGreaterThanOrEqual(2);
  }, 10_000);
});

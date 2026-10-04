import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActiveModelView, fieldLabel } from "@/components/model/active-model-view";

import { activeModelFixture, apiErrorBody, metricsFixture } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
// jsdom has no layout: the chart is replaced by a probe of the data it receives.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ data }: { data: unknown[] }) => (
    <pre data-testid="chart-data">{JSON.stringify(data)}</pre>
  ),
  Bar: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

const URL_ACTIVE = "http://localhost:3000/api/v1/model/active";

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("ActiveModelView", () => {
  it("shows the version, the reliability of each figure, the low-accuracy banner and the chart", async () => {
    server.use(http.get(URL_ACTIVE, () => HttpResponse.json(activeModelFixture())));
    renderWithClient(<ActiveModelView />, makeNoRetryClient());
    expect(await screen.findByText("Active version: v3")).toBeTruthy();
    expect(screen.getByText(/Activated on 2026-10-04 10:02 UTC/)).toBeTruthy();
    expect(screen.getAllByTestId("reliability-row").map((row) => row.textContent)).toEqual([
      "Click-through rate: Low (R² -0.03)",
      "Conversion rate: Low (R² -0.03)",
      "Website visits: Low (R² -0.03)",
    ]);
    expect(screen.getByRole("alert").textContent).toContain("The current model has low accuracy.");
    expect(JSON.parse(screen.getByTestId("chart-data").textContent ?? "[]")).toEqual([
      { name: "Ad spend (USD)", share: 60 },
      { name: "Channel", share: 40 },
    ]);
    await userEvent.click(screen.getByRole("button", { name: "Website visits" }));
    expect(screen.getByTestId("importance-chart").getAttribute("aria-label")).toContain(
      "Website visits",
    );
  });

  it("shows no banner when the model is reliable", async () => {
    server.use(
      http.get(URL_ACTIVE, () =>
        HttpResponse.json(
          activeModelFixture({ reliability: "good", metrics: metricsFixture("good") }),
        ),
      ),
    );
    renderWithClient(<ActiveModelView />, makeNoRetryClient());
    await screen.findByText("Active version: v3");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("explains that no model is active yet", async () => {
    server.use(
      http.get(URL_ACTIVE, () =>
        HttpResponse.json(apiErrorBody("NO_ACTIVE_MODEL", "No model is active."), { status: 409 }),
      ),
    );
    renderWithClient(<ActiveModelView />, makeNoRetryClient());
    expect(
      await screen.findByText(
        "No active model yet. An administrator must train and activate a model.",
      ),
    ).toBeTruthy();
  });

  it("turns a field name into its glossary label", () => {
    expect(fieldLabel("previous_purchases")).toBe("Previous purchases");
    expect(fieldLabel("something_else")).toBe("something_else");
  });
});

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PredictView } from "@/components/predict/predict-view";

import { apiErrorBody, predictionFixture } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: () => null,
  Bar: () => null,
  Cell: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

const BASE = "http://localhost:3000/api/v1";
const OPTIONS = {
  currency: "USD",
  enums: {},
  limits: {},
  training_ranges: {},
  features_used: ["ad_spend"],
  optional_categories: {},
  model_version: { id: "22222222-2222-4222-8222-222222222222", version: 3 },
};
const DEFAULTS = {
  pages_per_visit: 5.4,
  time_on_site: 7.8,
  social_shares: 50,
  email_opens: 9,
  email_clicks: 5,
  basis: "channel_and_type",
};

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
  server.use(
    http.get(`${BASE}/reference/options`, () => HttpResponse.json(OPTIONS)),
    http.get(`${BASE}/reference/engagement-defaults`, () => HttpResponse.json(DEFAULTS)),
  );
});

describe("PredictView", () => {
  it("shows a banner and no form when no model is active", async () => {
    server.use(
      http.get(`${BASE}/reference/options`, () =>
        HttpResponse.json({ ...OPTIONS, model_version: null }),
      ),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    expect((await screen.findByRole("status")).textContent).toContain("No active model yet");
    expect(screen.queryByRole("button", { name: "Predict" })).toBeNull();
  });

  it("pre-fills the engagement, predicts on click and re-predicts when a change is applied", async () => {
    const bodies: Record<string, unknown>[] = [];
    server.use(
      http.post(`${BASE}/predictions/simulate`, async ({ request }) => {
        bodies.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(predictionFixture());
      }),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    const pages = (await screen.findByLabelText("Pages per visit")) as HTMLInputElement;
    await waitFor(() => expect(pages.value).toBe("5.4"));
    expect(screen.getByText("Expected engagement")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Predict" }));
    expect(await screen.findAllByTestId("figure-card")).toHaveLength(5);
    expect(bodies[0]).toMatchObject({ campaign_channel: "Email", ad_spend: 5000, email_clicks: 5 });
    expect(bodies[0]).not.toHaveProperty("advertising_platform");

    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatchObject({ campaign_channel: "PPC" });
    expect((screen.getByLabelText("Channel") as HTMLSelectElement).value).toBe("PPC");
  });

  it("refuses an out-of-range value without calling the API", async () => {
    const simulate = vi.fn();
    server.use(
      http.post(`${BASE}/predictions/simulate`, () => {
        simulate();
        return HttpResponse.json(predictionFixture());
      }),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    const age = await screen.findByLabelText("Age");
    await userEvent.clear(age);
    await userEvent.type(age, "17");
    await userEvent.click(screen.getByRole("button", { name: "Predict" }));
    expect(await screen.findByText("Enter a value between 18 and 100.")).toBeTruthy();
    expect(simulate).not.toHaveBeenCalled();
  });

  it("shows the message of the API when the prediction fails", async () => {
    server.use(
      http.post(`${BASE}/predictions/simulate`, () =>
        HttpResponse.json(apiErrorBody("NO_ACTIVE_MODEL", "No model is active yet."), {
          status: 409,
        }),
      ),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    await userEvent.click(await screen.findByRole("button", { name: "Predict" }));
    expect((await screen.findByRole("alert")).textContent).toBe("No model is active yet.");
  });
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HistoryTable } from "@/components/history/history-table";
import { PredictionDetail } from "@/components/history/prediction-detail";
import { SavePrediction } from "@/components/predict/save-prediction";
import type { PredictionResult } from "@/hooks/use-prediction";

import { apiErrorBody, predictionFixture } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push }) }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));
// jsdom has no layout: the chart is replaced by nothing.
vi.mock("@/components/predict/drivers-chart", () => ({ DriversChart: () => null }));

const BASE = "http://localhost:3000/api/v1/predictions";
const ID = "33333333-3333-4333-8333-333333333333";
const INPUT = { campaign_channel: "Email", campaign_type: "Conversion", ad_spend: 5000 };

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("HistoryTable", () => {
  it("lists name, date, level and model version with a link to the detail", async () => {
    server.use(
      http.get(BASE, () =>
        HttpResponse.json({
          items: [
            {
              id: ID,
              name: "Spring push",
              created_at: "2026-10-04T10:30:00Z",
              level: "medium",
              model_version: 3,
            },
          ],
        }),
      ),
    );
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    const row = await screen.findByTestId("history-row");
    expect(row.textContent).toContain("Spring push");
    expect(row.textContent).toContain("2026-10-04 10:30 UTC");
    expect(row.textContent).toContain("Medium");
    expect(row.textContent).toContain("v3");
    expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe(`/history/${ID}`);
  });

  it("says so when nothing is saved yet", async () => {
    server.use(http.get(BASE, () => HttpResponse.json({ items: [] })));
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    expect(await screen.findByText(/No saved prediction yet/)).toBeTruthy();
  });
});

describe("SavePrediction", () => {
  it("sends only the name and the campaign, with a default name", async () => {
    let body: unknown = null;
    server.use(
      http.post(BASE, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(predictionFixture({ id: ID }), { status: 201 });
      }),
    );
    const result = predictionFixture({ input: INPUT }) as unknown as PredictionResult;
    renderWithClient(<SavePrediction result={result} />, makeNoRetryClient());
    await userEvent.click(screen.getByRole("button", { name: "Save prediction" }));
    const name = screen.getByLabelText("Name");
    expect((name as HTMLInputElement).value).toBe("Email Conversion");
    await userEvent.clear(name);
    await userEvent.type(name, "Spring push");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(body).toEqual({ name: "Spring push", input: INPUT }));
    expect(await screen.findByTestId("saved-notice")).toBeTruthy();
  });

  it("refuses an empty name before any request", async () => {
    const result = predictionFixture({ input: INPUT }) as unknown as PredictionResult;
    renderWithClient(<SavePrediction result={result} />, makeNoRetryClient());
    await userEvent.click(screen.getByRole("button", { name: "Save prediction" }));
    await userEvent.clear(screen.getByLabelText("Name"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Enter a name of at most 100 characters.")).toBeTruthy();
  });
});

describe("PredictionDetail", () => {
  it("shows the frozen results without any Apply button, then deletes", async () => {
    let deleted = false;
    server.use(
      http.get(`${BASE}/${ID}`, () =>
        HttpResponse.json(
          predictionFixture({
            id: ID,
            label: "Spring push",
            created_at: "2026-10-04T10:30:00Z",
            input: INPUT,
          }),
        ),
      ),
      http.delete(`${BASE}/${ID}`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithClient(<PredictionDetail id={ID} />, makeNoRetryClient());
    expect((await screen.findByTestId("prediction-name")).textContent).toBe("Spring push");
    expect(screen.getByText("Saved on 2026-10-04 10:30 UTC with model version v3")).toBeTruthy();
    expect(screen.getByTestId("level-badge").textContent).toBe("Low");
    expect(screen.getByTestId("recommendation")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }),
    );
    await waitFor(() => expect(deleted).toBe(true));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/history"));
  });

  it("shows the message of the API when the prediction is not yours", async () => {
    server.use(
      http.get(`${BASE}/${ID}`, () =>
        HttpResponse.json(apiErrorBody("NOT_FOUND", "Prediction not found."), { status: 404 }),
      ),
    );
    renderWithClient(<PredictionDetail id={ID} />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toBe("Prediction not found.");
  });
});

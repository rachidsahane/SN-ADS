import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActiveModelView } from "@/components/model/active-model-view";
import { fieldLabel, fieldLabelShort } from "@/lib/field-labels";

import { activeModelFixture, apiErrorBody, metricsFixture } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const URL_ACTIVE = "http://localhost:3000/api/v1/model/active";

beforeEach(() => {
  vi.resetAllMocks();
  process.env.TZ = "UTC";
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("ActiveModelView", () => {
  it("shows the five facts, the reliability table, the low-accuracy banner and the importance bars", async () => {
    server.use(http.get(URL_ACTIVE, () => HttpResponse.json(activeModelFixture())));
    renderWithClient(<ActiveModelView />, makeNoRetryClient());

    const facts = within(await screen.findByTestId("model-facts"));
    expect(facts.getByText("Version")).toBeTruthy();
    expect(facts.getByText("v3")).toBeTruthy();
    expect(facts.getByText("Oct 4, 2026, 10:02")).toBeTruthy();
    expect(facts.getByText("All data")).toBeTruthy();
    expect(facts.getByText("6,398")).toBeTruthy();
    expect(facts.getByText("1,602")).toBeTruthy();

    // Figure | Reliability | R² | Mean error | Error if always guessing the average
    const rows = screen
      .getAllByTestId("reliability-row")
      .map((row) => Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent));
    expect(rows).toEqual([
      ["Click-through rate", "Low", "-0.03", "0.0733", "0.0725"],
      ["Conversion rate", "Low", "-0.03", "0.0733", "0.0725"],
      ["Website visits", "Low", "-0.03", "12.40", "12.30"],
    ]);
    expect(
      screen.getByText("Low: R² below 0.10 · Moderate: 0.10 to 0.40 · Good: 0.40 and above."),
    ).toBeTruthy();

    // The low-accuracy banner is information (blue), not an alert.
    expect(screen.getByRole("note").textContent).toContain("The current model has low accuracy.");
    expect(screen.queryByRole("alert")).toBeNull();

    const chart = within(screen.getByTestId("importance-chart"));
    expect(chart.getByText("Ad spend")).toBeTruthy();
    expect(chart.getByText("60%")).toBeTruthy();
    expect(chart.getByText("40%")).toBeTruthy();
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
    await screen.findByTestId("model-facts");
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("is busy (skeleton) while the model loads", () => {
    server.use(http.get(URL_ACTIVE, () => new Promise(() => undefined)));
    const { container } = renderWithClient(<ActiveModelView />, makeNoRetryClient());
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
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

  it("shows the API message when the model cannot be read", async () => {
    server.use(
      http.get(URL_ACTIVE, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<ActiveModelView />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Back-end is down.");
  });
});

describe("field labels", () => {
  it("turns a field name into its glossary label", () => {
    expect(fieldLabel("previous_purchases")).toBe("Previous purchases");
    expect(fieldLabel("something_else")).toBe("something_else");
  });

  it("drops the unit for lists", () => {
    expect(fieldLabelShort("ad_spend")).toBe("Ad spend");
    expect(fieldLabelShort("income")).toBe("Income");
    expect(fieldLabelShort("age")).toBe("Age");
  });
});

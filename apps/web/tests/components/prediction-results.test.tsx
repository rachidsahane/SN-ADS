import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PredictionResults } from "@/components/predict/prediction-results";
import type { PredictionResult } from "@/hooks/use-prediction";

import { predictionFixture } from "../helpers/fixtures";

function renderResults(overrides: Partial<Record<string, unknown>> = {}, onApply = vi.fn()) {
  const result = predictionFixture({
    input: { campaign_channel: "Email", campaign_type: "Conversion", ad_spend: 5000 },
    ...overrides,
  }) as unknown as PredictionResult;
  render(<PredictionResults result={result} onApply={onApply} />);
  return onApply;
}

describe("PredictionResults (prototype layout)", () => {
  it("shows the three figures with the dataset average under each", () => {
    renderResults();
    expect(screen.getAllByTestId("figure-card").map((card) => card.textContent)).toEqual([
      "Click-through rate12.10%Dataset average 15.42%",
      "Conversion rate4.08%Dataset average 10.38%",
      "Website visits36.1Dataset average 24.7",
    ]);
  });

  it("leaves the average out for a model that did not store it", () => {
    const base = predictionFixture() as unknown as PredictionResult;
    renderResults({ performance: { ...base.performance, averages: undefined } });
    expect(screen.getAllByTestId("figure-card")[0]?.textContent).toBe("Click-through rate12.10%");
  });

  it("shows the level word, the score, the scale and the three notes", () => {
    renderResults();
    expect(screen.getByTestId("level-badge").textContent).toBe("Low");
    expect(screen.getByTestId("score").textContent).toBe("Score 31.3 / 100");
    expect(screen.getByText("Low below 40.4 · High from 59.6")).toBeTruthy();
    expect(screen.getByText("note 43")).toBeTruthy();
    expect(screen.getByText("Estimated leads")).toBeTruthy();
    expect(screen.getByText("1.47")).toBeTruthy();
    expect(screen.getByText("$3,397.87")).toBeTruthy();
    expect(
      screen.getByText(/Each note ranks this campaign against the Conversion campaigns/),
    ).toBeTruthy();
  });

  it("says 'all' when the score fell back to every campaign type", () => {
    const base = predictionFixture() as unknown as PredictionResult;
    renderResults({ performance: { ...base.performance, reference: "all_types" } });
    expect(screen.getByText(/against the all campaigns/)).toBeTruthy();
  });

  it("shows n/a when no lead is expected", () => {
    renderResults({ derived: { estimated_leads: 0, estimated_cost_per_result: null } });
    expect(screen.getByText("n/a")).toBeTruthy();
  });

  it("shows the low-reliability note with a link to the Model page, and no alert for field warnings", () => {
    renderResults({
      warnings: [
        {
          code: "LOW_MODEL_RELIABILITY",
          field: null,
          message: "The current model has low accuracy.",
        },
        { code: "OUT_OF_TRAINING_RANGE", field: "ad_spend", message: "Outside." },
      ],
    });
    const note = screen.getByTestId("reliability-note");
    expect(note.textContent).toContain("The current model has low accuracy.");
    expect(
      within(note).getByRole("link", { name: "See model reliability" }).getAttribute("href"),
    ).toBe("/model");
    expect(screen.queryByText("Outside.")).toBeNull(); // shown under the field, not here
  });

  it("shows the five-or-fewer driver rows of the selected figure with signed values", async () => {
    renderResults();
    const rows = () => screen.getAllByTestId("driver-row").map((row) => row.textContent);
    expect(rows()).toEqual(["Ad spend$5,000+0.40 pp", "ChannelEmail−0.20 pp"]);
    await userEvent.click(screen.getByRole("tab", { name: "Website visits" }));
    expect(rows()).toEqual(["Ad spend$5,000+0.00", "ChannelEmail−0.00"]);
    expect(screen.getByRole("tab", { name: "Website visits" }).getAttribute("aria-selected")).toBe(
      "true",
    );
  });

  it("shows a recommendation card with the before and after table, and applies it", async () => {
    const onApply = renderResults();
    const card = screen.getByTestId("recommendation");
    expect(card.textContent).toContain("Channel");
    expect(card.textContent).toContain("+36.3 pts");
    expect(card.textContent).toContain("Email → PPC");
    expect(card.textContent).toContain("Score31.367.6");
    expect(card.textContent).toContain("LevelLowHigh");
    await userEvent.click(within(card).getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ lever: "campaign_channel" }));
  });

  it("says so when no change is worth proposing", () => {
    renderResults({ recommendations: { status: "none_significant", items: [] } });
    expect(screen.getByText(/No tested change improves the result significantly\./)).toBeTruthy();
    expect(screen.getByText(/Tested: every other channel and type/)).toBeTruthy();
    expect(screen.queryByTestId("recommendation")).toBeNull();
  });
});

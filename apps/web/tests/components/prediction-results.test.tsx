import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PredictionResults } from "@/components/predict/prediction-results";
import type { PredictionResult } from "@/hooks/use-prediction";

import { predictionFixture } from "../helpers/fixtures";

// jsdom has no layout: the chart is replaced by a probe of the data it receives.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ data }: { data: unknown[] }) => (
    <pre data-testid="chart-data">{JSON.stringify(data)}</pre>
  ),
  Bar: () => null,
  Cell: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

function renderResults(overrides: Partial<Record<string, unknown>> = {}, onApply = vi.fn()) {
  const result = predictionFixture(overrides) as unknown as PredictionResult;
  render(<PredictionResults result={result} onApply={onApply} busy={false} />);
  return onApply;
}

describe("PredictionResults", () => {
  it("shows the five cards, the level with its score and the three notes", () => {
    renderResults();
    expect(screen.getAllByTestId("figure-card").map((card) => card.textContent)).toEqual([
      "Click-through rate12.10%",
      "Conversion rate4.08%",
      "Website visits36.11",
      "Estimated leads1.47",
      "Estimated cost per result$3,397.87",
    ]);
    expect(screen.getByTestId("level-badge").textContent).toBe("Low");
    expect(screen.getByTestId("score").textContent).toBe("31.3 / 100");
    expect(screen.getByText("Estimated leads: 30.8 / 100")).toBeTruthy();
    expect(screen.getByTestId("warning").textContent).toContain("Ad spend (USD): Outside");
  });

  it("shows no cost when no lead is expected", () => {
    renderResults({ derived: { estimated_leads: 0, estimated_cost_per_result: null } });
    expect(screen.getAllByTestId("figure-card")[4]?.textContent).toContain("n/a");
  });

  it("lists the drivers of the selected figure in tabs", async () => {
    renderResults();
    const data = () => JSON.parse(screen.getByTestId("chart-data").textContent ?? "[]");
    expect(data()).toEqual([
      { name: "Ad spend (USD)", amount: 0.4, direction: "up" },
      { name: "Channel", amount: 0.2, direction: "down" },
    ]);
    await userEvent.click(screen.getByRole("tab", { name: "Website visits" }));
    expect(data()[0].amount).toBe(0.004);
  });

  it("describes a recommendation and applies it", async () => {
    const onApply = renderResults();
    const item = screen.getByTestId("recommendation");
    expect(item.textContent).toContain(
      "Change channel from Email to PPC: +36.3 points (Low -> High)",
    );
    await userEvent.click(within(item).getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ lever: "campaign_channel" }));
  });

  it("says so when no change is worth proposing", () => {
    renderResults({ recommendations: { status: "none_significant", items: [] } });
    expect(screen.getByText("No tested change improves the result significantly.")).toBeTruthy();
    expect(screen.queryByTestId("recommendation")).toBeNull();
  });
});

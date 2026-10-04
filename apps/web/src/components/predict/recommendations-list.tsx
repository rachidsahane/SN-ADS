"use client";

import { Button } from "@/components/ui/button";
import type { PredictionResult } from "@/hooks/use-prediction";
import { labels } from "@/lib/labels";

type Recommendation = PredictionResult["recommendations"]["items"][number];

function show(value: string | number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString("en-US") : String(value ?? "");
}

/** Phrase d'une recommandation : « Change channel from Email to PPC: +6.1 points (Medium -> High) ». */
export function describe(item: Recommendation, level: PredictionResult["performance"]["level"]) {
  const lever = (labels.predict.levers as Record<string, string>)[item.lever] ?? item.lever;
  return labels.predict.change(
    lever,
    show(item.from_value),
    show(item.to_value),
    item.score_gain,
    labels.predict.level[level],
    labels.predict.level[item.new_level],
  );
}

export function RecommendationsList({
  result,
  onApply,
  disabled,
}: {
  result: PredictionResult;
  /** Absent on a saved prediction: its results are frozen, nothing to apply. */
  onApply?: (item: Recommendation) => void;
  disabled?: boolean;
}) {
  const { status, items } = result.recommendations;
  return (
    <section className="flex flex-col gap-2">
      <h2>{labels.predict.recommendationsTitle}</h2>
      {status === "none_significant" ? (
        <p className="text-sm">{labels.predict.noRecommendation}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li
              key={item.lever}
              data-testid="recommendation"
              className="flex flex-wrap items-center justify-between gap-2 border border-border px-3 py-2 text-sm"
            >
              <span>{describe(item, result.performance.level)}</span>
              {onApply ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={disabled}
                  onClick={() => onApply(item)}
                >
                  {labels.predict.apply}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

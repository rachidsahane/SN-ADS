import { Button } from "@/components/ui/button";
import { formatFieldValue } from "@/components/predict/drivers-panel";
import { Tag } from "@/components/ui/tag";
import type { PredictionResult } from "@/hooks/use-prediction";
import { fieldLabelShort } from "@/lib/field-labels";
import { formatPercent, formatVisits } from "@/lib/format";
import { labels } from "@/lib/labels";

export type Recommendation = PredictionResult["recommendations"]["items"][number];

/** « Recommended changes » : jusqu'à trois cartes (un levier chacune) avec le avant / après et le bouton « Apply ». */
export function RecommendationsPanel({
  result,
  onApply,
}: {
  result: PredictionResult;
  onApply?: (item: Recommendation) => void;
}) {
  const { status, items } = result.recommendations;
  const { predictions, performance } = result;
  const g = labels.glossary;
  return (
    <div className="blueprint flex flex-col gap-[14px] p-[18px]">
      <div>
        <h4 className="m-0">{labels.predict.recommendationsTitle}</h4>
        <div className="text-xs text-neutral-700">{labels.predict.recommendationsHint}</div>
      </div>
      {status === "none_significant" || items.length === 0 ? (
        <div className="border border-dashed border-divider p-[14px] text-sm">
          {labels.predict.noRecommendation}
          <div className="mt-1 text-xs text-neutral-700">
            {labels.predict.noRecommendationTested}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
          {items.map((item) => {
            const rows = [
              [
                g.clickThroughRate,
                formatPercent(predictions.click_through_rate),
                formatPercent(item.new_predictions.click_through_rate),
              ],
              [
                g.conversionRate,
                formatPercent(predictions.conversion_rate),
                formatPercent(item.new_predictions.conversion_rate),
              ],
              [
                g.websiteVisits,
                formatVisits(predictions.website_visits),
                formatVisits(item.new_predictions.website_visits),
              ],
              [labels.predict.scoreRow, performance.score.toFixed(1), item.new_score.toFixed(1)],
              [
                labels.predict.levelRow,
                labels.predict.level[performance.level],
                labels.predict.level[item.new_level],
              ],
            ] as const;
            return (
              <div
                key={item.lever}
                data-testid="recommendation"
                className="flex flex-col gap-[10px] border border-divider p-[14px]"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <div className="kicker">{fieldLabelShort(item.lever)}</div>
                  <Tag tone="accent" className="num">
                    {labels.predict.gain(item.score_gain.toFixed(1))}
                  </Tag>
                </div>
                <div className="font-heading text-[19px] font-semibold leading-[1.2]">
                  {formatFieldValue(item.lever, item.from_value)} →{" "}
                  {formatFieldValue(item.lever, item.to_value)}
                </div>
                <table className="table !text-xs">
                  <thead>
                    <tr>
                      <th className="!px-0 !py-1" />
                      <th className="!px-0 !py-1 !text-right">{labels.predict.now}</th>
                      <th className="!px-0 !py-1 !text-right">{labels.predict.after}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(([name, now, after]) => (
                      <tr key={name}>
                        <td className="!px-0 !py-1">{name}</td>
                        <td className="num !px-0 !py-1 text-right text-neutral-700">{now}</td>
                        <td className="num !px-0 !py-1 text-right font-medium">{after}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {onApply ? (
                  <Button variant="outline" onClick={() => onApply(item)}>
                    {labels.predict.apply}
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

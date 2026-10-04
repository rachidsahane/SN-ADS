import type { PredictionResult } from "@/hooks/use-prediction";
import { formatPercent, formatVisits } from "@/lib/format";
import { labels } from "@/lib/labels";

/** Les trois chiffres prédits (prototype : valeur en 44 px condensé, moyenne du jeu de données dessous). */
export function MetricCards({ result }: { result: PredictionResult }) {
  const { predictions, performance } = result;
  const g = labels.glossary;
  const averages = performance.averages;
  const cards = [
    {
      label: g.clickThroughRate,
      value: formatPercent(predictions.click_through_rate),
      average: averages ? formatPercent(averages.click_through_rate) : null,
    },
    {
      label: g.conversionRate,
      value: formatPercent(predictions.conversion_rate),
      average: averages ? formatPercent(averages.conversion_rate) : null,
    },
    {
      label: g.websiteVisits,
      value: formatVisits(predictions.website_visits),
      average: averages ? formatVisits(averages.website_visits) : null,
    },
  ];
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-[18px]">
      {cards.map((card) => (
        <div
          key={card.label}
          data-testid="figure-card"
          className="blueprint flex flex-col gap-1 p-4"
        >
          <div className="kicker">{card.label}</div>
          <div className="num font-heading text-[44px] font-normal leading-none tracking-[-0.01em]">
            {card.value}
          </div>
          <div className="min-h-[18px] text-xs text-neutral-700">
            {card.average ? labels.predict.datasetAverage(card.average) : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

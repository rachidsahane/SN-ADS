import type { PredictionResult } from "@/hooks/use-prediction";
import { formatMoney, formatPercent } from "@/lib/format";
import { labels } from "@/lib/labels";

const LEVEL_COLOR = {
  low: "text-neutral-700",
  medium: "text-brand-700",
  high: "text-brand-800",
} as const;

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

/** Niveau de performance, échelle Low / Medium / High avec repère du score, trois notes et leur explication. */
export function PerformancePanel({ result }: { result: PredictionResult }) {
  const { performance, derived, predictions, input } = result;
  const { thresholds, notes } = performance;
  const low = thresholds.low_below;
  const high = thresholds.high_from;
  const score = clampPercent(performance.score);
  const cost = derived.estimated_cost_per_result;
  const noteRows = [
    {
      label: labels.glossary.clickThroughRate,
      value: formatPercent(predictions.click_through_rate),
      note: notes.click_through_rate,
    },
    {
      label: labels.glossary.estimatedLeads,
      value: derived.estimated_leads.toFixed(2),
      note: notes.estimated_leads,
    },
    {
      label: labels.glossary.estimatedCostPerResult,
      value: cost === null ? labels.predict.noLeads : formatMoney(cost),
      note: notes.estimated_cost_per_result,
    },
  ];
  const scope =
    performance.reference === "campaign_type" ? input.campaign_type : labels.predict.allTypes;
  const cellClass =
    "flex items-center justify-center text-[11px] uppercase tracking-[0.08em] text-neutral-700";

  return (
    <div className="blueprint flex flex-col gap-4 p-[18px]">
      <div className="flex flex-wrap items-end gap-7">
        <div className="flex-none">
          <div className="kicker">{labels.predict.levelTitle}</div>
          <div
            data-testid="level-badge"
            className={`font-heading text-[56px] font-normal leading-none ${LEVEL_COLOR[performance.level]}`}
          >
            {labels.predict.level[performance.level]}
          </div>
          <div data-testid="score" className="num text-[13px] text-neutral-700">
            {labels.predict.score(performance.score.toFixed(1))}
          </div>
        </div>
        <div className="flex min-w-[240px] flex-[1_1_280px] flex-col gap-1.5">
          <div
            className="relative grid h-7 border border-divider"
            style={{
              gridTemplateColumns: `${low}fr ${Math.max(high - low, 0)}fr ${Math.max(100 - high, 0)}fr`,
            }}
          >
            <div className={cellClass}>{labels.predict.level.low}</div>
            <div className={`${cellClass} border-x border-divider bg-brand-100`}>
              {labels.predict.level.medium}
            </div>
            <div className={cellClass}>{labels.predict.level.high}</div>
            <div
              aria-hidden="true"
              className="absolute -bottom-1.5 -top-1.5 -ml-px w-0.5 bg-brand-800 transition-[left] duration-300"
              style={{ left: `${score}%` }}
            />
          </div>
          <div className="num flex justify-between text-[11px] text-neutral-700">
            <span>0</span>
            <span>{labels.predict.scaleRange(low.toFixed(1), high.toFixed(1))}</span>
            <span>100</span>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4 border-t border-divider pt-[14px]">
        {noteRows.map((row) => (
          <div key={row.label} className="flex flex-col gap-1.5">
            <div className="flex justify-between gap-2 text-xs text-neutral-700">
              <span>{row.label}</span>
              <span className="num">{labels.predict.noteLabel(row.note.toFixed(0))}</span>
            </div>
            <div className="num font-heading text-[22px] font-semibold">{row.value}</div>
            <div className="h-1 bg-neutral-200">
              <div
                className="h-full bg-brand transition-[width] duration-300"
                style={{ width: `${clampPercent(row.note).toFixed(1)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="text-xs text-neutral-700">{labels.predict.referenceNote(scope)}</div>
    </div>
  );
}

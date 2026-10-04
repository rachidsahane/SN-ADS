"use client";

import { fieldLabel } from "@/components/model/active-model-view";
import { DriversChart } from "@/components/predict/drivers-chart";
import { RecommendationsList } from "@/components/predict/recommendations-list";
import { Alert } from "@/components/ui/alert";
import type { PredictionResult } from "@/hooks/use-prediction";
import { formatMoney, formatPercent } from "@/lib/format";
import { labels } from "@/lib/labels";
import { cn } from "@/lib/utils";

type Recommendation = PredictionResult["recommendations"]["items"][number];

const LEVEL_STYLE = {
  low: "bg-danger-soft text-destructive border-destructive/50",
  medium: "bg-background text-foreground border-border",
  high: "bg-success-soft text-success border-success/50",
} as const;

function Card({ title, value }: { title: string; value: string }) {
  return (
    <div data-testid="figure-card" className="flex flex-col gap-1 border border-border p-3">
      <span className="text-sm text-muted-foreground">{title}</span>
      <span className="text-xl font-semibold">{value}</span>
    </div>
  );
}

/** Résultats d'une simulation : cinq cartes, niveau, notes, avertissements, facteurs, conseils. */
export function PredictionResults({
  result,
  onApply,
  busy = false,
}: {
  result: PredictionResult;
  onApply?: (item: Recommendation) => void;
  busy?: boolean;
}) {
  const { predictions, derived, performance } = result;
  const g = labels.glossary;
  const cost = derived.estimated_cost_per_result;
  const notes = [
    [g.clickThroughRate, performance.notes.click_through_rate],
    [g.estimatedLeads, performance.notes.estimated_leads],
    [g.estimatedCostPerResult, performance.notes.estimated_cost_per_result],
  ] as const;
  return (
    <div className="flex flex-col gap-6" aria-busy={busy}>
      <h2>{labels.predict.resultsTitle}</h2>
      {result.warnings.map((warning) => (
        <Alert key={`${warning.code}-${warning.field}`} role="status" data-testid="warning">
          {warning.field ? `${fieldLabel(warning.field)}: ` : ""}
          {warning.message}
        </Alert>
      ))}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Card title={g.clickThroughRate} value={formatPercent(predictions.click_through_rate)} />
        <Card title={g.conversionRate} value={formatPercent(predictions.conversion_rate)} />
        <Card title={g.websiteVisits} value={predictions.website_visits.toLocaleString("en-US")} />
        <Card title={g.estimatedLeads} value={derived.estimated_leads.toLocaleString("en-US")} />
        <Card
          title={g.estimatedCostPerResult}
          value={cost === null ? labels.predict.noLeads : formatMoney(cost)}
        />
      </div>
      <section className="flex flex-col gap-2">
        <h2>{labels.predict.levelTitle}</h2>
        <div className="flex items-center gap-3">
          <span
            data-testid="level-badge"
            className={cn("border px-3 py-1 font-semibold", LEVEL_STYLE[performance.level])}
          >
            {labels.predict.level[performance.level]}
          </span>
          <span data-testid="score">{labels.predict.score(performance.score)}</span>
        </div>
        <p className="text-sm text-muted-foreground">{labels.predict.notesTitle}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {notes.map(([name, value]) => (
            <li key={name}>{labels.predict.note(name, value)}</li>
          ))}
        </ul>
      </section>
      <DriversChart drivers={result.drivers} />
      <RecommendationsList result={result} onApply={onApply} disabled={busy} />
    </div>
  );
}

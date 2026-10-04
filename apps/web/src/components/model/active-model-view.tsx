"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { type ActiveModel, useActiveModel } from "@/hooks/use-active-model";
import { apiMessage } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";

const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate],
  ["conversion_rate", labels.glossary.conversionRate],
  ["website_visits", labels.glossary.websiteVisits],
] as const;
type Figure = (typeof FIGURES)[number][0];

/** `ad_spend` -> « Ad spend (USD) » (glossaire du PRD) ; un champ inconnu reste tel quel. */
export function fieldLabel(field: string): string {
  const key = field.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
  const known = (labels.glossary as Record<string, string>)[key];
  return known ?? field;
}

function Importance({ model }: { model: ActiveModel }) {
  const [figure, setFigure] = useState<Figure>("click_through_rate");
  const name = FIGURES.find(([key]) => key === figure)?.[1] ?? "";
  const data = model.global_importance[figure]
    .slice(0, 10)
    .map((item) => ({ name: fieldLabel(item.field), share: Math.round(item.share * 1000) / 10 }));
  return (
    <section className="flex flex-col gap-2">
      <h2>{labels.model.importanceTitle}</h2>
      <p className="text-sm text-muted-foreground">{labels.model.importanceHint}</p>
      <div className="flex flex-wrap gap-2">
        {FIGURES.map(([key, text]) => (
          <Button
            key={key}
            size="sm"
            variant={key === figure ? "default" : "outline"}
            aria-pressed={key === figure}
            onClick={() => setFigure(key)}
          >
            {text}
          </Button>
        ))}
      </div>
      <div
        role="img"
        aria-label={labels.model.importanceFor(name)}
        data-testid="importance-chart"
        className="h-[360px] w-full max-w-3xl"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 16, right: 24 }}>
            <CartesianGrid horizontal={false} stroke="var(--color-divider)" />
            <XAxis type="number" unit="%" />
            <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value) => `${value}%`} />
            <Bar dataKey="share" fill="var(--color-accent-600)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

/** Page « Model » (PRD US-10) : version active, date, fiabilité par chiffre, importance globale. */
export function ActiveModelView() {
  const query = useActiveModel();
  if (query.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (query.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(query.error)}
      </Alert>
    );
  }
  const model = query.data;
  if (model === null) {
    return (
      <Alert role="status" className="mt-4">
        {labels.model.noActive}
      </Alert>
    );
  }
  return (
    <div className="mt-4 flex flex-col gap-6">
      <div>
        <p className="font-semibold">{labels.model.version(model.version)}</p>
        <p className="text-sm text-muted-foreground">
          {model.activated_at
            ? `${labels.model.activatedOn(formatDateTime(model.activated_at))} · `
            : ""}
          {labels.model.scope}
        </p>
      </div>
      {model.reliability === "low" ? (
        <Alert variant="destructive" role="alert">
          {labels.model.lowBanner}
        </Alert>
      ) : null}
      <section className="flex flex-col gap-2">
        <h2>{labels.model.reliabilityTitle}</h2>
        <p className="text-sm text-muted-foreground">{labels.model.reliabilityHint}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {FIGURES.map(([key, name]) => (
            <li key={key} data-testid="reliability-row">
              {`${name}: ${labels.reliability[model.metrics[key].reliability]} (R² ${model.metrics[key].r2.toFixed(2)})`}
            </li>
          ))}
        </ul>
      </section>
      <Importance model={model} />
    </div>
  );
}

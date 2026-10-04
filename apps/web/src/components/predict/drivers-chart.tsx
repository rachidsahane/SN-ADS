"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fieldLabel } from "@/components/model/active-model-view";
import { Button } from "@/components/ui/button";
import type { PredictionResult } from "@/hooks/use-prediction";
import { labels } from "@/lib/labels";

const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate, 100],
  ["conversion_rate", labels.glossary.conversionRate, 100],
  ["website_visits", labels.glossary.websiteVisits, 1],
] as const;

/** « What drives these predictions » : trois onglets, cinq barres horizontales par chiffre. */
export function DriversChart({ drivers }: { drivers: PredictionResult["drivers"] }) {
  const [selected, setSelected] = useState(0);
  const [figure, name, scale] = FIGURES[selected] ?? FIGURES[0];
  const data = drivers[figure].map((driver) => ({
    name: fieldLabel(driver.field),
    amount: Math.round(Math.abs(driver.contribution) * scale * 1000) / 1000,
    direction: driver.direction,
  }));
  const unit = scale === 100 ? " pt" : "";
  return (
    <section className="flex flex-col gap-2">
      <h2>{labels.predict.driversTitle}</h2>
      <p className="text-sm text-muted-foreground">{labels.predict.driversHint}</p>
      <div role="tablist" className="flex flex-wrap gap-2">
        {FIGURES.map(([key, text], index) => (
          <Button
            key={key}
            role="tab"
            size="sm"
            variant={index === selected ? "default" : "outline"}
            aria-selected={index === selected}
            onClick={() => setSelected(index)}
          >
            {text}
          </Button>
        ))}
      </div>
      <div
        role="img"
        aria-label={labels.predict.driversFor(name)}
        data-testid="drivers-chart"
        className="h-[260px] w-full max-w-3xl"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 16, right: 24 }}>
            <CartesianGrid horizontal={false} stroke="var(--color-divider)" />
            <XAxis type="number" unit={unit} />
            <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(value, _name, item) => [
                `${value}${unit}`,
                item.payload.direction === "up" ? labels.predict.up : labels.predict.down,
              ]}
            />
            <Bar dataKey="amount" isAnimationActive={false}>
              {data.map((item) => (
                <Cell key={item.name} fill={item.direction === "up" ? "#416180" : "#8a8a8a"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted-foreground">
        {`${labels.predict.up}: blue. ${labels.predict.down}: grey.`}
      </p>
    </section>
  );
}

"use client";

import { useState } from "react";

import { ArrowDownIcon, ArrowUpIcon } from "@/components/ui/icons";
import type { PredictionResult } from "@/hooks/use-prediction";
import { fieldLabelShort } from "@/lib/field-labels";
import { formatContribution, formatMoney, formatNumber } from "@/lib/format";
import { labels } from "@/lib/labels";

const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate, "rate"],
  ["conversion_rate", labels.glossary.conversionRate, "rate"],
  ["website_visits", labels.glossary.websiteVisits, "count"],
] as const;

/** Valeur d'un champ dans une liste : montants en dollars entiers, nombres avec séparateurs, texte tel quel. */
export function formatFieldValue(field: string, value: string | number | null | undefined): string {
  if (typeof value === "number") {
    return field === "ad_spend" || field === "income" ? formatMoney(value, 0) : formatNumber(value);
  }
  return value ?? "";
}

/** « What moved this prediction » : trois onglets, cinq barres divergentes (bleu = pousse vers le haut, gris = vers le bas). */
export function DriversPanel({ drivers }: { drivers: PredictionResult["drivers"] }) {
  const [selected, setSelected] = useState(0);
  const [figure, name, kind] = FIGURES[selected] ?? FIGURES[0];
  const rows = drivers[figure].slice(0, 5);
  const max = Math.max(...rows.map((row) => Math.abs(row.contribution)), 0) || 1;

  return (
    <div className="blueprint flex flex-col gap-[14px] p-[18px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="m-0">{labels.predict.driversTitle}</h4>
          <div className="text-xs text-neutral-700">{labels.predict.driversHint}</div>
        </div>
        <div className="seg" role="tablist">
          {FIGURES.map(([key, text], index) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={index === selected}
              onClick={() => setSelected(index)}
            >
              {text}
            </button>
          ))}
        </div>
      </div>
      <div
        role="group"
        aria-label={labels.predict.driversFor(name)}
        data-testid="drivers-chart"
        className="flex flex-col"
      >
        {rows.map((row) => {
          const width = `${((Math.abs(row.contribution) / max) * 100).toFixed(1)}%`;
          const up = row.contribution >= 0;
          return (
            <div
              key={row.field}
              data-testid="driver-row"
              className="grid grid-cols-[minmax(120px,1.2fr)_minmax(0,2fr)_84px] items-center gap-3 border-b border-[color-mix(in_srgb,var(--color-text)_8%,transparent)] py-2"
            >
              <div className="min-w-0">
                <div className="text-sm">{fieldLabelShort(row.field)}</div>
                <div className="text-xs text-neutral-700">
                  {formatFieldValue(row.field, row.value)}
                </div>
              </div>
              <div className="grid h-3 grid-cols-2">
                <div className="flex justify-end border-r border-foreground">
                  <div className="h-full bg-neutral-500" style={{ width: up ? "0%" : width }} />
                </div>
                <div className="flex">
                  <div className="h-full bg-brand" style={{ width: up ? width : "0%" }} />
                </div>
              </div>
              <div className="num flex items-center justify-end gap-1 text-[13px]">
                {up ? (
                  <ArrowUpIcon className="stroke-brand-700" />
                ) : (
                  <ArrowDownIcon className="stroke-neutral-700" />
                )}
                <span aria-label={up ? labels.predict.up : labels.predict.down}>
                  {formatContribution(row.contribution, kind)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

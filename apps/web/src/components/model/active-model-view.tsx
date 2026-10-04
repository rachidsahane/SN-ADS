"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { type ActiveModel, useActiveModel } from "@/hooks/use-active-model";
import { apiMessage } from "@/lib/api/messages";
import { fieldLabelShort } from "@/lib/field-labels";
import { formatDateTime, formatShare } from "@/lib/format";
import { labels } from "@/lib/labels";

const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate, 4],
  ["conversion_rate", labels.glossary.conversionRate, 4],
  ["website_visits", labels.glossary.websiteVisits, 2],
] as const;
type Figure = (typeof FIGURES)[number][0];

const TOP_INPUTS = 8;

function count(value: number | null): string {
  return value === null ? labels.admin.audit.none : value.toLocaleString("en-US");
}

function Facts({ model }: { model: ActiveModel }) {
  const f = labels.model.facts;
  const facts = [
    [f.version, `v${model.version}`],
    [
      f.activated,
      model.activated_at ? formatDateTime(model.activated_at) : labels.admin.audit.none,
    ],
    [f.scope, labels.model.allData],
    [f.train, count(model.train_row_count)],
    [f.test, count(model.holdout_row_count)],
  ] as const;
  return (
    <div
      data-testid="model-facts"
      className="stat-grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))]"
    >
      {facts.map(([key, value]) => (
        <div key={key} className="p-[14px]">
          <div className="kicker">{key}</div>
          <div className="num font-heading text-[22px] font-semibold">{value}</div>
        </div>
      ))}
    </div>
  );
}

function ReliabilityPanel({ model }: { model: ActiveModel }) {
  const c = labels.model.columns;
  return (
    <div className="blueprint flex flex-col gap-2.5 p-[18px]">
      <h4 className="m-0">{labels.model.reliabilityTitle}</h4>
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>{c.figure}</th>
              <th>{c.reliability}</th>
              <th className="!text-right">{c.r2}</th>
              <th className="!text-right">{c.mae}</th>
              <th className="!text-right">{c.baseline}</th>
            </tr>
          </thead>
          <tbody>
            {FIGURES.map(([key, name, decimals]) => {
              const metrics = model.metrics[key];
              return (
                <tr key={key} data-testid="reliability-row">
                  <td>{name}</td>
                  <td>
                    <Tag tone="neutral">{labels.reliability[metrics.reliability]}</Tag>
                  </td>
                  <td className="num text-right">{metrics.r2.toFixed(2)}</td>
                  <td className="num text-right">{metrics.mae.toFixed(decimals)}</td>
                  <td className="num text-right">{metrics.baseline_mae.toFixed(decimals)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-neutral-700">{labels.model.reliabilityScale}</div>
    </div>
  );
}

/** Importance globale : barres CSS (aucun graphique), les huit premiers champs du chiffre choisi. */
function ImportancePanel({ model }: { model: ActiveModel }) {
  const [figure, setFigure] = useState<Figure>("click_through_rate");
  const name = FIGURES.find(([key]) => key === figure)?.[1] ?? "";
  const rows = model.global_importance[figure].slice(0, TOP_INPUTS);
  const max = Math.max(...rows.map((row) => row.share), 0) || 1;
  return (
    <div className="blueprint flex flex-col gap-[14px] p-[18px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="m-0">{labels.model.importanceTitle}</h4>
          <div className="text-xs text-neutral-700">{labels.model.importanceHint}</div>
        </div>
        <div className="seg">
          {FIGURES.map(([key, text]) => (
            <button
              key={key}
              type="button"
              aria-pressed={key === figure}
              onClick={() => setFigure(key)}
            >
              {text}
            </button>
          ))}
        </div>
      </div>
      <div
        role="group"
        aria-label={labels.model.importanceFor(name)}
        data-testid="importance-chart"
        className="flex flex-col gap-2"
      >
        {rows.map((row) => (
          <div
            key={row.field}
            className="grid grid-cols-[minmax(130px,200px)_minmax(0,1fr)_48px] items-center gap-3 text-sm"
          >
            <div>{fieldLabelShort(row.field)}</div>
            <div className="h-3 bg-neutral-200">
              <div
                className="h-full bg-brand"
                style={{ width: `${((row.share / max) * 100).toFixed(0)}%` }}
              />
            </div>
            <div className="num text-right">{formatShare(row.share)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ModelSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-[22px]">
      <Skeleton className="h-12" />
      <Skeleton className="h-[72px]" />
      <Skeleton className="h-[200px]" />
      <Skeleton className="h-[330px]" />
    </div>
  );
}

/** Page « Model » (PRD US-10) : version active, fiabilité mesurée, importance globale des champs. */
export function ActiveModelView() {
  const query = useActiveModel();
  if (query.isPending) {
    return <ModelSkeleton />;
  }
  if (query.isError) {
    return (
      <Alert variant="destructive" role="alert">
        {apiMessage(query.error)}
      </Alert>
    );
  }
  const model = query.data;
  if (model === null) {
    return <Alert role="status">{labels.model.noActive}</Alert>;
  }
  return (
    <>
      {model.reliability === "low" ? <Alert role="note">{labels.model.lowBanner}</Alert> : null}
      <Facts model={model} />
      <ReliabilityPanel model={model} />
      <ImportancePanel model={model} />
    </>
  );
}

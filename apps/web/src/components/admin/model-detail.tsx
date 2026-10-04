"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  type ModelVersionDetail,
  useActivateModel,
  useModelVersion,
} from "@/hooks/use-model-versions";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

type Metrics = NonNullable<ModelVersionDetail["metrics"]>;
const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate],
  ["conversion_rate", labels.glossary.conversionRate],
  ["website_visits", labels.glossary.websiteVisits],
] as const;

/** Quatre chiffres significatifs : 0.0733, 12.4, -0.0342. */
function figure(value: number): string {
  return Number(value.toPrecision(3)).toString();
}

function MetricsTable({ metrics }: { metrics: Metrics }) {
  const heads = labels.models.metrics;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            {[heads.figure, heads.mae, heads.rmse, heads.r2, heads.baseline, heads.reliability].map(
              (head) => (
                <th key={head} className="px-3 py-2 font-medium">
                  {head}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {FIGURES.map(([key, name]) => {
            const row = metrics[key];
            return (
              <tr key={key} data-testid="metrics-row" className="border-b border-border">
                <td className="px-3 py-2">{name}</td>
                <td className="px-3 py-2">{figure(row.mae)}</td>
                <td className="px-3 py-2">{figure(row.rmse)}</td>
                <td className="px-3 py-2">{figure(row.r2)}</td>
                <td className="px-3 py-2">{figure(row.baseline_mae)}</td>
                <td className="px-3 py-2">{labels.reliability[row.reliability]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Détail d'une version : statut, raison d'un échec, mesures par chiffre, bouton d'activation. */
export function ModelDetail({ id }: { id: string }) {
  const version = useModelVersion(id);
  const activate = useActivateModel(id);

  if (version.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (version.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(version.error)}
      </Alert>
    );
  }
  const data = version.data;
  const canActivate = data.status === "succeeded" && !data.is_active;
  return (
    <div className="mt-4 flex flex-col gap-4">
      <p>
        <Link href="/admin/models">{labels.models.back}</Link>
      </p>
      <h2>{labels.models.versionTitle(data.version)}</h2>
      <p data-testid="model-status">
        {labels.models.status[data.status]}
        {data.is_active ? ` · ${labels.models.active}` : ""}
      </p>
      {data.status === "queued" || data.status === "running" ? (
        <p className="text-sm text-muted-foreground">{labels.models.inProgress}</p>
      ) : null}
      {data.status === "failed" && data.error_message ? (
        <Alert variant="destructive" role="alert">
          {labels.models.errorReason(data.error_message)}
        </Alert>
      ) : null}
      {data.metrics ? (
        <section className="flex flex-col gap-2">
          <h3>{labels.models.metricsTitle}</h3>
          {data.train_row_count !== null && data.holdout_row_count !== null ? (
            <p className="text-sm text-muted-foreground">
              {labels.models.rows(data.train_row_count, data.holdout_row_count)}
            </p>
          ) : null}
          <MetricsTable metrics={data.metrics} />
          <p className="text-sm text-muted-foreground">
            {`${labels.model.reliabilityTitle}: ${labels.reliability[data.metrics.overall_reliability]}`}
          </p>
        </section>
      ) : null}
      {activate.isSuccess ? (
        <Alert variant="success" role="status">
          {labels.models.activated}
        </Alert>
      ) : null}
      {activate.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(activate.error)}
        </Alert>
      ) : null}
      {canActivate ? (
        <div>
          <Button onClick={() => activate.mutate()} disabled={activate.isPending}>
            {activate.isPending ? labels.models.activating : labels.models.activate}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

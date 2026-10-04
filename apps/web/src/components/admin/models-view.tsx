"use client";

import { useEffect, useRef, useState } from "react";

import { PageTitle } from "@/components/layout/page-title";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { SpinnerIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { type ActiveModel, useActiveModel } from "@/hooks/use-active-model";
import { useDatasetSummary } from "@/hooks/use-dataset-summary";
import {
  type ModelVersion,
  type ModelVersionDetail,
  useActivateModel,
  useModelVersion,
  useModelVersions,
  useTrainModel,
} from "@/hooks/use-model-versions";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { useToast } from "@/providers/toast-provider";

type Status = ModelVersion["status"];
const STATUS_TONE: Record<Status, "neutral" | "accent"> = {
  queued: "neutral",
  running: "accent",
  succeeded: "accent",
  failed: "neutral",
};
const FIGURES = [
  ["click_through_rate", labels.glossary.clickThroughRate, 4],
  ["conversion_rate", labels.glossary.conversionRate, 4],
  ["website_visits", labels.glossary.websiteVisits, 2],
] as const;
type Metrics = NonNullable<ModelVersionDetail["metrics"]>;

function scopeLabel(scope: string): string {
  return (labels.models.scope as Record<string, string>)[scope] ?? scope;
}

/** Moyenne des rapports d'erreur moyenne (cette version / version active) : 1 ou moins = au moins aussi fiable. */
export function errorRatio(next: Metrics, active: Metrics): number {
  const ratios = FIGURES.map(([key]) => next[key].mae / active[key].mae);
  return ratios.reduce((sum, ratio) => sum + ratio, 0) / ratios.length;
}

function Comparison({
  metrics,
  active,
  name,
}: {
  metrics: Metrics;
  active: ActiveModel;
  name: number;
}) {
  const c = labels.models.compare;
  const good = errorRatio(metrics, active.metrics) <= 1;
  return (
    <>
      <table className="table !text-[13px]" data-testid="compare-table">
        <thead>
          <tr>
            <th>{c.title}</th>
            <th className="!text-right">{`v${active.version}`}</th>
            <th className="!text-right">{`v${name}`}</th>
            <th className="!text-right">{c.change}</th>
          </tr>
        </thead>
        <tbody>
          {FIGURES.map(([key, label, decimals]) => {
            const previous = active.metrics[key].mae;
            const next = metrics[key].mae;
            const change = ((next - previous) / previous) * 100;
            return (
              <tr key={key}>
                <td>{label}</td>
                <td className="num text-right">{previous.toFixed(decimals)}</td>
                <td className="num text-right">{next.toFixed(decimals)}</td>
                <td className="num text-right">{`${change > 0 ? "+" : ""}${change.toFixed(2)}%`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div
        data-testid="verdict"
        className={`text-sm font-medium ${good ? "text-brand-700" : "text-neutral-800"}`}
      >
        {good ? labels.models.verdict.good : labels.models.verdict.bad}
      </div>
    </>
  );
}

function DetailPanel({ id, onActivated }: { id: string; onActivated: (version: number) => void }) {
  const version = useModelVersion(id);
  const active = useActiveModel();
  const activate = useActivateModel(id);

  if (version.isPending) {
    return (
      <div
        className="blueprint flex min-w-0 flex-[1_1_360px] flex-col gap-[14px] p-[18px]"
        aria-busy="true"
      >
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-28" />
      </div>
    );
  }
  if (version.isError) {
    return (
      <div className="min-w-0 flex-[1_1_360px]">
        <Alert variant="destructive" role="alert">
          {apiMessage(version.error)}
        </Alert>
      </div>
    );
  }
  const data = version.data;
  const done = data.status === "succeeded";
  const inProgress = data.status === "queued" || data.status === "running";
  const activeModel = active.data ?? null;
  const comparable = done && !data.is_active && data.metrics !== null && activeModel !== null;
  const worse =
    comparable && data.metrics !== null && activeModel !== null
      ? errorRatio(data.metrics, activeModel.metrics) > 1
      : false;

  async function activateNow() {
    try {
      await activate.mutateAsync();
    } catch {
      return; // l'erreur s'affiche dans le panneau
    }
    onActivated(data?.version ?? 0);
  }

  return (
    <div
      data-testid="model-detail"
      className="blueprint flex min-w-0 flex-[1_1_360px] flex-col gap-[14px] p-[18px]"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="m-0">{labels.models.versionTitle(data.version)}</h3>
        <Tag tone={STATUS_TONE[data.status]} data-testid="model-status">
          {labels.models.status[data.status]}
        </Tag>
      </div>
      <div className="text-[13px] text-neutral-700">
        {labels.models.meta(
          scopeLabel(data.data_scope),
          data.requested_by?.full_name ?? labels.models.unknownRequester,
          formatDateTime(data.created_at),
        )}
      </div>
      {inProgress ? (
        <div className="flex items-center gap-2.5 border border-dashed border-divider p-[14px] text-sm">
          <SpinnerIcon size={16} />
          {labels.models.progress[data.status as "queued" | "running"]}
        </div>
      ) : null}
      {data.status === "failed" ? (
        <div className="notice !border-brand-700 !p-3">
          {data.error_message ?? labels.models.detailFailed}
        </div>
      ) : null}
      {comparable && data.metrics && activeModel ? (
        <Comparison metrics={data.metrics} active={activeModel} name={data.version} />
      ) : null}
      {done && !data.is_active && !active.isPending && activeModel === null ? (
        <div className="text-[13px] text-neutral-700">{labels.models.noCompare}</div>
      ) : null}
      {activate.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(activate.error)}
        </Alert>
      ) : null}
      {done && !data.is_active ? (
        <Button
          blueprint
          className="self-start"
          disabled={worse || activate.isPending || active.isPending}
          onClick={() => void activateNow()}
        >
          {activate.isPending ? labels.models.activating : labels.models.activate}
        </Button>
      ) : null}
      {data.is_active ? (
        <div className="text-[13px] text-brand-700">{labels.models.isActive}</div>
      ) : null}
    </div>
  );
}

function TrainDialog({
  open,
  onClose,
  onStarted,
}: {
  open: boolean;
  onClose: () => void;
  onStarted: (id: string) => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={labels.models.dialog.title}>
      <TrainForm onClose={onClose} onStarted={onStarted} />
    </Dialog>
  );
}

function TrainForm({
  onClose,
  onStarted,
}: {
  onClose: () => void;
  onStarted: (id: string) => void;
}) {
  const d = labels.models.dialog;
  const train = useTrainModel();
  const summary = useDatasetSummary();
  const { toast } = useToast();
  const agencyReady = (summary.data?.agency_rows ?? 0) >= labels.data.agencyMinimum;

  async function start() {
    try {
      const created = await train.mutateAsync();
      onStarted(created.id);
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "TRAINING_ALREADY_RUNNING") {
        toast(labels.models.alreadyRunning);
        onClose();
        return;
      }
      if (isUnexpectedError(error)) {
        reportError(error, {
          route: "train-dialog",
          requestId: error instanceof ApiError ? error.requestId : null,
        });
      }
    }
  }

  return (
    <>
      <div className="text-[13px] text-neutral-700">{d.text}</div>
      {train.isError &&
      !(train.error instanceof ApiError && train.error.code === "TRAINING_ALREADY_RUNNING") ? (
        <Alert variant="destructive" role="alert" className="!px-3 !py-2 !text-[13px]">
          {apiMessage(train.error)}
        </Alert>
      ) : null}
      <div className="flex flex-col gap-2.5">
        <label className="radio">
          <input type="radio" name="scope" checked readOnly />
          <span className="dot" />
          {d.all} <span className="text-xs text-neutral-700">{d.allHint}</span>
        </label>
        <label className="radio" style={{ opacity: agencyReady ? 1 : 0.45 }}>
          <input type="radio" name="scope" disabled />
          <span className="dot" />
          {d.agency}
        </label>
        {agencyReady ? null : (
          <div className="ml-6 text-xs text-neutral-700">
            {d.agencyRequires(labels.data.agencyMinimum)}
          </div>
        )}
      </div>
      <div className="dialog-actions">
        <Button variant="outline" onClick={onClose}>
          {d.cancel}
        </Button>
        <Button disabled={train.isPending} onClick={() => void start()}>
          {train.isPending ? labels.models.training : d.start}
        </Button>
      </div>
    </>
  );
}

function ModelsSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-wrap items-start gap-6">
      <div className="flex min-w-0 flex-[1_1_440px] flex-col gap-1">
        <Skeleton className="h-8" />
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-11 opacity-70" />
        ))}
      </div>
      <Skeleton className="h-[260px] min-w-0 flex-[1_1_360px]" />
    </div>
  );
}

/**
 * Page « Models » (prototype) : tableau des versions à gauche, panneau de détail à droite (progression, échec,
 * comparaison avec la version active, verdict, activation) et fenêtre « Train a new version ».
 * Rechargée toutes les 3 secondes tant qu'un apprentissage est en cours.
 */
export function ModelsView({ initialId }: { initialId?: string }) {
  const versions = useModelVersions();
  const { toast } = useToast();
  const [selected, setSelected] = useState<string | null>(initialId ?? null);
  const [trainOpen, setTrainOpen] = useState(false);
  const rows = versions.data?.items;

  // Version affichée : celle qu'on a choisie, sinon la version active, sinon la plus récente.
  const current = selected ?? (rows?.find((row) => row.is_active) ?? rows?.[0])?.id ?? null;

  // « Model vN finished training. » quand une version en cours se termine pendant qu'on regarde la page.
  const previous = useRef<Map<string, Status> | null>(null);
  useEffect(() => {
    if (!rows) {
      return;
    }
    const before = previous.current;
    if (before) {
      for (const row of rows) {
        const was = before.get(row.id);
        if ((was === "queued" || was === "running") && row.status === "succeeded") {
          toast(labels.models.finished(row.version));
        }
      }
    }
    previous.current = new Map(rows.map((row) => [row.id, row.status]));
  }, [rows, toast]);

  const error = versions.error;
  useEffect(() => {
    if (error && isUnexpectedError(error)) {
      reportError(error, {
        route: "models-view",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  const c = labels.models.columns;
  return (
    <>
      <PageTitle
        subtitle={labels.models.subtitle}
        actions={
          <Button blueprint onClick={() => setTrainOpen(true)}>
            {labels.models.train}
          </Button>
        }
      >
        {labels.models.title}
      </PageTitle>
      {versions.isPending ? (
        <ModelsSkeleton />
      ) : versions.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(versions.error)}
        </Alert>
      ) : rows && rows.length === 0 ? (
        <div className="blueprint p-10 text-center text-neutral-700">{labels.models.empty}</div>
      ) : (
        <div className="flex flex-wrap items-start gap-6">
          <div className="min-w-0 flex-[1_1_440px] overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>{c.version}</th>
                  <th>{c.status}</th>
                  <th>{c.scope}</th>
                  <th>{c.requestedBy}</th>
                  <th>{c.created}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows?.map((version) => (
                  <tr
                    key={version.id}
                    data-testid="model-row"
                    aria-selected={version.id === current}
                    tabIndex={0}
                    className={`cursor-pointer ${version.id === current ? "!bg-brand-100" : ""}`}
                    onClick={() => setSelected(version.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelected(version.id);
                      }
                    }}
                  >
                    <td className="font-heading text-base font-semibold">{`v${version.version}`}</td>
                    <td className="whitespace-nowrap">
                      <Tag tone={STATUS_TONE[version.status]} data-testid="row-status">
                        {labels.models.status[version.status]}
                      </Tag>
                      {version.is_active ? (
                        <Tag tone="outline" className="ml-1.5">
                          {labels.models.active}
                        </Tag>
                      ) : null}
                    </td>
                    <td>{scopeLabel(version.data_scope)}</td>
                    <td>{version.requested_by?.full_name ?? labels.admin.audit.none}</td>
                    <td className="num whitespace-nowrap">{formatDateTime(version.created_at)}</td>
                    <td className="text-right">
                      <span className="text-[13px] text-brand-700">{labels.models.review}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {current ? (
            <DetailPanel
              key={current}
              id={current}
              onActivated={(v) => toast(labels.models.activated(v))}
            />
          ) : null}
        </div>
      )}
      <TrainDialog
        open={trainOpen}
        onClose={() => setTrainOpen(false)}
        onStarted={(id) => setSelected(id)}
      />
    </>
  );
}

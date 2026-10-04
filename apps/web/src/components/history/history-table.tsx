"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TrashIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { useDeletePrediction, usePredictionList } from "@/hooks/use-predictions";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { useToast } from "@/providers/toast-provider";

const LEVEL_TONE = { low: "neutral", medium: "accent", high: "outline" } as const;

function HistorySkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-1">
      <Skeleton className="h-8" />
      {[0, 1, 2, 3].map((row) => (
        <Skeleton key={row} className="h-10 opacity-70" />
      ))}
    </div>
  );
}

/** Les 50 dernières prédictions enregistrées par l'utilisateur connecté (prototype : 8 colonnes, suppression en ligne). */
export function HistoryTable() {
  const list = usePredictionList();
  const remove = useDeletePrediction();
  const { toast } = useToast();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const error = list.error;
  useEffect(() => {
    if (error && isUnexpectedError(error)) {
      reportError(error, {
        route: "history-table",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  if (list.isPending) {
    return <HistorySkeleton />;
  }
  if (list.isError) {
    return (
      <Alert variant="destructive" role="alert">
        {apiMessage(list.error)}
      </Alert>
    );
  }
  const rows = list.data.items;
  if (rows.length === 0) {
    return (
      <div className="blueprint p-10 text-center text-neutral-700">{labels.history.empty}</div>
    );
  }
  const heads = labels.history.columns;

  async function confirmDelete(id: string) {
    setFailure(null);
    try {
      await remove.mutateAsync(id);
    } catch (caught) {
      setFailure(apiMessage(caught));
      return;
    }
    setConfirming(null);
    toast(labels.history.deleted);
  }

  return (
    <>
      {failure ? (
        <Alert variant="destructive" role="alert">
          {failure}
        </Alert>
      ) : null}
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>{heads.name}</th>
              <th>{heads.date}</th>
              <th>{heads.channel}</th>
              <th>{heads.type}</th>
              <th>{heads.level}</th>
              <th className="!text-right">{heads.score}</th>
              <th>{heads.model}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-testid="history-row">
                <td>
                  <Link
                    href={`/history/${row.id}`}
                    className="btn btn-ghost !px-0 !py-0.5 !font-sans !text-sm !font-medium"
                  >
                    {row.name}
                  </Link>
                </td>
                <td className="num whitespace-nowrap">{formatDateTime(row.created_at)}</td>
                <td>{row.campaign_channel}</td>
                <td>{row.campaign_type}</td>
                <td>
                  <Tag tone={LEVEL_TONE[row.level]}>{labels.predict.level[row.level]}</Tag>
                </td>
                <td className="num text-right">{row.score.toFixed(1)}</td>
                <td>{labels.history.version(row.model_version)}</td>
                <td className="whitespace-nowrap text-right">
                  {confirming === row.id ? (
                    <>
                      <span className="mr-1.5 text-xs">{labels.history.deleteAsk}</span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={remove.isPending}
                        onClick={() => void confirmDelete(row.id)}
                      >
                        {labels.history.delete}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                        {labels.history.cancel}
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={labels.history.deleteAria}
                      onClick={() => {
                        setFailure(null);
                        setConfirming(row.id);
                      }}
                    >
                      <TrashIcon />
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

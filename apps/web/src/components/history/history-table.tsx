"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { usePredictionList } from "@/hooks/use-predictions";
import { apiMessage } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";

/** Les 50 dernières prédictions enregistrées par l'utilisateur connecté. */
export function HistoryTable() {
  const list = usePredictionList();
  if (list.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (list.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(list.error)}
      </Alert>
    );
  }
  const rows = list.data.items;
  if (rows.length === 0) {
    return <p className="mt-4 text-sm text-muted-foreground">{labels.history.empty}</p>;
  }
  const heads = labels.history.columns;
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            {[heads.name, heads.date, heads.level, heads.version].map((head) => (
              <th key={head} className="px-3 py-2 font-medium">
                {head}
              </th>
            ))}
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-testid="history-row" className="border-b border-border">
              <td className="px-3 py-2">{row.name}</td>
              <td className="whitespace-nowrap px-3 py-2">{formatDateTime(row.created_at)}</td>
              <td className="px-3 py-2">{labels.predict.level[row.level]}</td>
              <td className="px-3 py-2">{labels.history.version(row.model_version)}</td>
              <td className="px-3 py-2">
                <Link href={`/history/${row.id}`}>{labels.history.open}</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

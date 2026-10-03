"use client";

import { useEffect } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { type AuditEntry, useAdminAudit } from "@/hooks/use-admin-audit";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

/** Valeur de métadonnée en texte simple (jamais du HTML : React échappe, SEC-14). */
function asText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** Journal d'audit en lecture seule (PRD US-05) : cinq colonnes, plus récent en premier (ordre de l'API). */
export function AuditTable() {
  const audit = useAdminAudit();
  const rows = audit.data?.pages.flatMap((page) => page.items) ?? [];
  const error = audit.error;

  useEffect(() => {
    if (error && isUnexpectedError(error)) {
      reportError(error, {
        route: "audit-table",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  if (audit.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (audit.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(audit.error)}
      </Alert>
    );
  }
  if (rows.length === 0) {
    return <p className="mt-4 text-sm text-muted-foreground">{labels.admin.audit.empty}</p>;
  }
  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-2 font-medium">{labels.admin.audit.columns.date}</th>
              <th className="px-3 py-2 font-medium">{labels.admin.audit.columns.author}</th>
              <th className="px-3 py-2 font-medium">{labels.admin.audit.columns.action}</th>
              <th className="px-3 py-2 font-medium">{labels.admin.audit.columns.target}</th>
              <th className="px-3 py-2 font-medium">{labels.admin.audit.columns.details}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((entry) => (
              <AuditRow key={entry.id} entry={entry} />
            ))}
          </tbody>
        </table>
      </div>
      {audit.hasNextPage ? (
        <div>
          <Button
            variant="outline"
            onClick={() => void audit.fetchNextPage()}
            disabled={audit.isFetchingNextPage}
          >
            {audit.isFetchingNextPage ? labels.admin.users.loading : labels.admin.audit.loadMore}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const email = entry.metadata.email;
  const target = typeof email === "string" ? email : entry.target_id;
  return (
    <tr data-testid="audit-row" className="border-b border-border align-top">
      <td className="whitespace-nowrap px-3 py-2">{formatDateTime(entry.created_at)}</td>
      <td className="px-3 py-2">
        {entry.actor ? entry.actor.full_name : labels.admin.audit.system}
      </td>
      <td className="px-3 py-2">
        <code data-testid="audit-action" className="font-mono text-xs">
          {entry.action}
        </code>
      </td>
      <td className="px-3 py-2">
        <span className="text-muted-foreground">{entry.target_type}</span> <span>{target}</span>
      </td>
      <td className="px-3 py-2">
        {Object.entries(entry.metadata)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, value]) => (
            <div key={key}>{`${key}: ${asText(value)}`}</div>
          ))}
      </td>
    </tr>
  );
}

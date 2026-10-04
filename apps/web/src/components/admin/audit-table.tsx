"use client";

import { useEffect, useMemo } from "react";

import { PageTitle } from "@/components/layout/page-title";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type AuditEntry, useAdminAudit } from "@/hooks/use-admin-audit";
import { useAdminUsers } from "@/hooks/use-admin-users";
import { useModelVersions } from "@/hooks/use-model-versions";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

const a = labels.admin.audit;

type Lookups = {
  /** Numéro de version par identifiant de version. */
  versions: Map<string, number>;
  /** Nom complet par identifiant d'utilisateur. */
  users: Map<string, string>;
};

/** Valeur de métadonnée en texte simple (jamais du HTML : React échappe, SEC-14). */
function asText(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function metaText(entry: AuditEntry, key: string): string | null {
  const value = (entry.metadata as Record<string, unknown>)[key];
  return value === undefined || value === null ? null : asText(value);
}

/** Cible lisible (« Model v3 », « Fatou D. ») au lieu de l'identifiant brut. */
export function targetLabel(entry: AuditEntry, lookups: Lookups): string {
  if (entry.target_type === "model_version") {
    const version = lookups.versions.get(entry.target_id);
    return version === undefined ? a.modelUnknown : a.model(version);
  }
  if (entry.target_type === "user") {
    return lookups.users.get(entry.target_id) ?? metaText(entry, "email") ?? entry.target_type;
  }
  return metaText(entry, "file_name") ?? entry.target_id;
}

/** Phrase de détail d'une entrée (prototype : « Replaced v1 », « Role: marketer », « 6,412 training rows · 1,588 test rows »). */
export function detailsText(
  entry: AuditEntry,
  entries: AuditEntry[],
  lookups: Lookups,
  hasMore: boolean,
): string {
  switch (entry.action) {
    case "user.invited": {
      const role = metaText(entry, "role");
      return role ? a.role(role) : a.none;
    }
    case "user.role_changed": {
      const from = metaText(entry, "from");
      const to = metaText(entry, "to");
      return from && to ? a.roleChange(from, to) : a.none;
    }
    case "model.training_requested": {
      const scope = metaText(entry, "data_scope");
      return scope ? a.scope(scope) : a.none;
    }
    case "model.training_succeeded": {
      const train = metaText(entry, "train_rows");
      const test = metaText(entry, "test_rows");
      return train && test ? a.rows(Number(train), Number(test)) : a.none;
    }
    case "model.training_failed":
      return metaText(entry, "reason") ?? a.none;
    case "model.activated": {
      // La version remplacée est celle de l'activation précédente, plus bas dans la liste (plus ancienne).
      const index = entries.indexOf(entry);
      const earlier = entries.slice(index + 1).find((e) => e.action === "model.activated");
      const version = earlier ? lookups.versions.get(earlier.target_id) : undefined;
      if (version !== undefined) {
        return a.replaced(version);
      }
      return earlier || hasMore ? a.none : a.firstActive;
    }
    default:
      return a.none;
  }
}

function AuditSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-1">
      <Skeleton className="h-8" />
      {[0, 1, 2, 3, 4, 5].map((row) => (
        <Skeleton key={row} className="h-10 opacity-70" />
      ))}
    </div>
  );
}

/** Journal d'audit en lecture seule (PRD US-05) : cinq colonnes, plus récent en premier (ordre de l'API). */
export function AuditTable() {
  const audit = useAdminAudit();
  const versions = useModelVersions();
  const users = useAdminUsers();
  const rows = useMemo(() => audit.data?.pages.flatMap((page) => page.items) ?? [], [audit.data]);
  const error = audit.error;

  const lookups = useMemo<Lookups>(
    () => ({
      versions: new Map(versions.data?.items.map((v) => [v.id, v.version]) ?? []),
      users: new Map(
        users.data?.pages.flatMap((page) => page.items).map((u) => [u.id, u.full_name]) ?? [],
      ),
    }),
    [versions.data, users.data],
  );

  useEffect(() => {
    if (error && isUnexpectedError(error)) {
      reportError(error, {
        route: "audit-table",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  // Le tableau attend aussi les noms et les numéros de version (une requête chacun, en parallèle).
  const waiting = audit.isPending || versions.isPending || users.isPending;

  return (
    <>
      <PageTitle subtitle={a.subtitle}>{a.title}</PageTitle>
      {waiting ? (
        <AuditSkeleton />
      ) : audit.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(audit.error)}
        </Alert>
      ) : rows.length === 0 ? (
        <div className="blueprint p-10 text-center text-neutral-700">{a.empty}</div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>{a.columns.date}</th>
                  <th>{a.columns.author}</th>
                  <th>{a.columns.action}</th>
                  <th>{a.columns.target}</th>
                  <th>{a.columns.details}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((entry) => (
                  <tr key={entry.id} data-testid="audit-row">
                    <td className="num whitespace-nowrap">{formatDateTime(entry.created_at)}</td>
                    <td>{entry.actor ? entry.actor.full_name : a.system}</td>
                    <td>
                      <code data-testid="audit-action" className="font-[monospace] text-xs">
                        {entry.action}
                      </code>
                    </td>
                    <td>{targetLabel(entry, lookups)}</td>
                    <td className="text-[13px] text-neutral-700">
                      {detailsText(entry, rows, lookups, audit.hasNextPage)}
                    </td>
                  </tr>
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
                {audit.isFetchingNextPage ? labels.admin.users.loading : a.loadMore}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}

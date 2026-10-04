"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useModelVersions, useTrainModel } from "@/hooks/use-model-versions";
import { apiMessage } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";

/** Versions du modèle (démonstration) : lancement d'un apprentissage et suivi du statut. */
export function ModelsTable() {
  const versions = useModelVersions();
  const train = useTrainModel();
  const rows = versions.data?.items ?? [];

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex justify-end">
        <Button onClick={() => train.mutate()} disabled={train.isPending}>
          {train.isPending ? labels.models.training : labels.models.train}
        </Button>
      </div>
      {train.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(train.error)}
        </Alert>
      ) : null}
      {versions.isPending ? (
        <p aria-busy="true" className="text-sm text-muted-foreground">
          {labels.admin.users.loading}
        </p>
      ) : versions.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(versions.error)}
        </Alert>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{labels.models.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2 font-medium">{labels.models.columns.version}</th>
                <th className="px-3 py-2 font-medium">{labels.models.columns.status}</th>
                <th className="px-3 py-2 font-medium">{labels.models.columns.requestedBy}</th>
                <th className="px-3 py-2 font-medium">{labels.models.columns.created}</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((version) => (
                <tr key={version.id} data-testid="model-row" className="border-b border-border">
                  <td className="px-3 py-2">
                    {`v${version.version}`}
                    {version.is_active ? (
                      <span className="ml-2 font-medium text-success">{labels.models.active}</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2" data-testid="model-status">
                    {labels.models.status[version.status]}
                  </td>
                  <td className="px-3 py-2">{version.requested_by?.full_name ?? "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {formatDateTime(version.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    <Link href={`/admin/models/${version.id}`}>{labels.models.open}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

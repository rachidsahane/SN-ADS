"use client";

import { Alert } from "@/components/ui/alert";
import { useDatasetSummary } from "@/hooks/use-dataset-summary";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

/** Résumé des données d'apprentissage (démonstration : jeu de départ uniquement, lignes de test). */
export function DataSummary() {
  const summary = useDatasetSummary();
  if (summary.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (summary.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(summary.error)}
      </Alert>
    );
  }
  const { seed_rows, agency_rows, holdout_rows } = summary.data;
  return (
    <div className="mt-4 flex flex-col gap-2">
      <ul className="flex flex-col gap-1 text-sm">
        <li>{labels.data.seedRows(seed_rows)}</li>
        <li>{labels.data.agencyRows(agency_rows)}</li>
        <li>{labels.data.testRows(holdout_rows)}</li>
      </ul>
      <p className="text-sm text-muted-foreground">{labels.data.testRowsHint}</p>
    </div>
  );
}

import type { Metadata } from "next";

import { HistoryTable } from "@/components/history/history-table";
import { PageShell } from "@/components/layout/page-shell";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.history.title };

/** Page « History » : les prédictions enregistrées par l'utilisateur connecté. */
export default function HistoryPage() {
  return (
    <PageShell>
      <PageTitle subtitle={labels.history.subtitle}>{labels.history.title}</PageTitle>
      <HistoryTable />
    </PageShell>
  );
}

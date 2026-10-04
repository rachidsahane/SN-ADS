import type { Metadata } from "next";

import { DataSummary } from "@/components/admin/data-summary";
import { PageShell } from "@/components/layout/page-shell";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.data.title };

/** Page « Data » : combien de lignes servent à apprendre, et les imports (démonstration). */
export default function DataPage() {
  return (
    <PageShell>
      <DataSummary />
    </PageShell>
  );
}

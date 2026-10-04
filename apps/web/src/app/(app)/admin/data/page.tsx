import type { Metadata } from "next";

import { DataSummary } from "@/components/admin/data-summary";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.data.title };

/** Page « Data » : combien de lignes servent à apprendre (démonstration). */
export default function DataPage() {
  return (
    <>
      <PageTitle>{labels.data.title}</PageTitle>
      <DataSummary />
    </>
  );
}

import type { Metadata } from "next";

import { ModelsTable } from "@/components/admin/models-table";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.models.title };

/** Page « Models » : versions, lancement d'un apprentissage (démonstration). */
export default function ModelsPage() {
  return (
    <>
      <PageTitle>{labels.models.title}</PageTitle>
      <ModelsTable />
    </>
  );
}

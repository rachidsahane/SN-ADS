import type { Metadata } from "next";

import { ModelDetail } from "@/components/admin/model-detail";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.models.title };

/** Détail d'une version : mesures et bouton « Activate this version ». */
export default async function ModelVersionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageTitle>{labels.models.title}</PageTitle>
      <ModelDetail id={id} />
    </>
  );
}

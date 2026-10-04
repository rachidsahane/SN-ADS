import type { Metadata } from "next";

import { ModelsView } from "@/components/admin/models-view";
import { PageShell } from "@/components/layout/page-shell";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.models.title };

/** Même écran que « Models », avec la version demandée déjà sélectionnée. */
export default async function ModelVersionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <PageShell>
      <ModelsView initialId={id} />
    </PageShell>
  );
}

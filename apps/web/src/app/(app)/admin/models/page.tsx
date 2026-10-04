import type { Metadata } from "next";

import { ModelsView } from "@/components/admin/models-view";
import { PageShell } from "@/components/layout/page-shell";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.models.title };

/** Page « Models » : versions, détail, comparaison avec la version active, apprentissage (démonstration). */
export default function ModelsPage() {
  return (
    <PageShell>
      <ModelsView />
    </PageShell>
  );
}

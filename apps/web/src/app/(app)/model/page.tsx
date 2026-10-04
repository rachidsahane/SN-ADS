import type { Metadata } from "next";

import { PageShell } from "@/components/layout/page-shell";
import { PageTitle } from "@/components/layout/page-title";
import { ActiveModelView } from "@/components/model/active-model-view";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.model.title };

/** Page « Model » pour tous : version active, fiabilité, importance globale. */
export default function ModelPage() {
  return (
    <PageShell>
      <PageTitle subtitle={labels.model.subtitle}>{labels.model.title}</PageTitle>
      <ActiveModelView />
    </PageShell>
  );
}

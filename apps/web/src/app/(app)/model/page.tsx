import type { Metadata } from "next";

import { ActiveModelView } from "@/components/model/active-model-view";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.model.title };

/** Page « Model » pour tous : version active, fiabilité, importance globale. */
export default function ModelPage() {
  return (
    <>
      <PageTitle>{labels.model.title}</PageTitle>
      <ActiveModelView />
    </>
  );
}

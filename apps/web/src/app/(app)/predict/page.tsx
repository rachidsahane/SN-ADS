import type { Metadata } from "next";

import { PageTitle } from "@/components/layout/page-title";
import { Alert } from "@/components/ui/alert";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.predict.title };

/**
 * Page Predict : vide jusqu'à la phase 10 (le formulaire arrive alors). Elle affiche l'avis
 * « pas d'accès » quand l'espace d'administration a renvoyé un marketer ici (PRD CL-08).
 */
export default async function PredictPage({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string }>;
}) {
  const { notice } = await searchParams;
  return (
    <>
      <PageTitle>{labels.predict.title}</PageTitle>
      {notice === "forbidden" ? (
        <Alert variant="destructive" role="alert" className="mt-4">
          {labels.errors.noAccess}
        </Alert>
      ) : null}
    </>
  );
}

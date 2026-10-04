import type { Metadata } from "next";

import { ForbiddenToast } from "@/components/layout/forbidden-toast";
import { PredictView } from "@/components/predict/predict-view";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.predict.title };

/**
 * Page Predict : formulaire de campagne et résultats en direct. Elle annonce aussi « pas d'accès »
 * quand l'espace d'administration a renvoyé un marketer ici (PRD CL-08).
 */
export default async function PredictPage({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string }>;
}) {
  const { notice } = await searchParams;
  return (
    <>
      {notice === "forbidden" ? <ForbiddenToast /> : null}
      <PredictView />
    </>
  );
}

import type { Metadata } from "next";

import { PredictionDetail } from "@/components/history/prediction-detail";
import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.history.title };

/** Détail d'une prédiction enregistrée (404 « Prediction not found. » si elle n'est pas à vous). */
export default async function PredictionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <>
      <PageTitle>{labels.history.title}</PageTitle>
      <PredictionDetail id={id} />
    </>
  );
}

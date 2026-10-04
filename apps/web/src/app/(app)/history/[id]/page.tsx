import type { Metadata } from "next";

import { PredictView } from "@/components/predict/predict-view";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.history.title };

/**
 * Prédiction enregistrée : le même écran que Predict, en lecture seule (résultats figés) jusqu'à la première
 * modification d'un champ. 404 « Prediction not found. » si elle n'est pas à vous.
 */
export default async function PredictionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PredictView savedId={id} />;
}

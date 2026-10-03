import type { Metadata } from "next";

import { PageTitle } from "@/components/layout/page-title";
import { labels } from "@/lib/labels";

export const metadata: Metadata = { title: labels.predict.title };

/** Page Predict : vide à la phase 2 (le formulaire arrive à la phase 10). */
export default function PredictPage() {
  return <PageTitle>{labels.predict.title}</PageTitle>;
}

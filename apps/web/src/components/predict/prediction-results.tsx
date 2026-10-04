"use client";

import Link from "next/link";

import { DriversPanel } from "@/components/predict/drivers-panel";
import { MetricCards } from "@/components/predict/metric-cards";
import { PerformancePanel } from "@/components/predict/performance-panel";
import {
  type Recommendation,
  RecommendationsPanel,
} from "@/components/predict/recommendations-panel";
import { InfoIcon } from "@/components/ui/icons";
import type { PredictionResult } from "@/hooks/use-prediction";
import { labels } from "@/lib/labels";

function Note({ children, testId }: { children: React.ReactNode; testId?: string }) {
  return (
    <div
      role="note"
      data-testid={testId}
      className="flex items-start gap-2.5 border border-brand bg-brand-100 px-[14px] py-2.5 text-[13px] text-brand-900"
    >
      <InfoIcon className="mt-0.5 flex-none" />
      <span>{children}</span>
    </div>
  );
}

/**
 * Colonne de résultats (prototype) : note de fiabilité, trois chiffres, niveau de performance, facteurs, conseils.
 * Les avertissements « hors des valeurs vues » s'affichent sous les champs du formulaire, pas ici.
 */
export function PredictionResults({
  result,
  onApply,
}: {
  result: PredictionResult;
  onApply?: (item: Recommendation) => void;
}) {
  const lowReliability = result.warnings.some((w) => w.code === "LOW_MODEL_RELIABILITY");
  const others = result.warnings.filter(
    (w) => w.code !== "LOW_MODEL_RELIABILITY" && w.code !== "OUT_OF_TRAINING_RANGE",
  );
  return (
    <>
      {lowReliability ? (
        <Note testId="reliability-note">
          {labels.predict.reliabilityNote}{" "}
          <Link href="/model" className="underline">
            {labels.predict.seeReliability}
          </Link>
        </Note>
      ) : null}
      {others.map((warning) => (
        <Note key={`${warning.code}-${warning.field}`} testId="warning">
          {warning.message}
        </Note>
      ))}
      <MetricCards result={result} />
      <PerformancePanel result={result} />
      <DriversPanel drivers={result.drivers} />
      <RecommendationsPanel result={result} onApply={onApply} />
    </>
  );
}

"use client";

import Link from "next/link";

import { PageShell } from "@/components/layout/page-shell";
import { PageTitle } from "@/components/layout/page-title";
import { PredictScreen } from "@/components/predict/predict-screen";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useReferenceOptions } from "@/hooks/use-prediction";
import { usePrediction } from "@/hooks/use-predictions";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

/** Page « Predict » pendant le chargement : même grille que l'écran final, des blocs gris à la place. */
export function PredictSkeleton() {
  return (
    <PageShell wide>
      <PageTitle subtitle={labels.predict.subtitle}>{labels.predict.title}</PageTitle>
      <div aria-busy="true" className="flex flex-wrap items-start gap-7">
        <div className="flex max-w-[480px] flex-[1_1_340px] flex-col gap-[22px]">
          <Skeleton className="h-[200px]" />
          <Skeleton className="h-[300px]" />
          <Skeleton className="h-[330px]" />
        </div>
        <div className="flex min-w-0 flex-[2_1_520px] flex-col gap-[22px]">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-[18px]">
            <Skeleton className="h-[112px]" />
            <Skeleton className="h-[112px]" />
            <Skeleton className="h-[112px]" />
          </div>
          <Skeleton className="h-[230px]" />
          <Skeleton className="h-[340px]" />
          <Skeleton className="h-[300px]" />
        </div>
      </div>
    </PageShell>
  );
}

/**
 * Page « Predict » : bandeau quand aucun modèle n'est actif, sinon formulaire et résultats en direct. Avec `savedId`,
 * affiche la prédiction enregistrée de l'historique (lecture seule jusqu'à la première modification).
 */
export function PredictView({ savedId }: { savedId?: string }) {
  const options = useReferenceOptions();
  const saved = usePrediction(savedId ?? "", savedId !== undefined);

  if (options.isError || (savedId !== undefined && saved.isError)) {
    const error = options.isError ? options.error : saved.error;
    return (
      <PageShell wide>
        <PageTitle subtitle={labels.predict.subtitle}>{labels.predict.title}</PageTitle>
        <Alert variant="destructive" role="alert">
          {apiMessage(error)}
        </Alert>
        {savedId !== undefined ? (
          <Link href="/history" className="btn btn-ghost self-start">
            {labels.history.back}
          </Link>
        ) : null}
      </PageShell>
    );
  }
  if (options.isPending || (savedId !== undefined && saved.isPending)) {
    return <PredictSkeleton />;
  }
  return (
    <PredictScreen
      key={`${options.data.model_version?.id ?? "none"}-${savedId ?? "new"}`}
      options={options.data}
      saved={savedId !== undefined ? (saved.data ?? null) : null}
    />
  );
}

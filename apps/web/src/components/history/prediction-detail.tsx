"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { fieldLabel } from "@/components/model/active-model-view";
import { PredictionResults } from "@/components/predict/prediction-results";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useDeletePrediction, usePrediction } from "@/hooks/use-predictions";
import { apiMessage } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";

/** Une prédiction enregistrée : campagne et résultats tels qu'ils étaient à l'enregistrement. */
export function PredictionDetail({ id }: { id: string }) {
  const router = useRouter();
  const prediction = usePrediction(id);
  const remove = useDeletePrediction(id);
  const [confirming, setConfirming] = useState(false);

  const back = (
    <Link href="/history" className="text-sm">
      {labels.history.back}
    </Link>
  );
  if (prediction.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (prediction.isError) {
    return (
      <div className="mt-4 flex flex-col gap-3">
        <Alert variant="destructive" role="alert">
          {apiMessage(prediction.error)}
        </Alert>
        {back}
      </div>
    );
  }
  const result = prediction.data;
  const inputs = Object.entries(result.input).filter(([, value]) => value !== null);

  async function confirmDelete() {
    try {
      await remove.mutateAsync();
    } catch {
      return; // the error is shown in the dialog
    }
    router.push("/history");
  }

  return (
    <div className="mt-4 flex flex-col gap-6">
      {back}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 data-testid="prediction-name">{result.label}</h2>
          <p className="text-sm text-muted-foreground">
            {labels.history.summary(
              result.created_at ? formatDateTime(result.created_at) : "",
              result.model_version.version,
            )}
          </p>
        </div>
        <Button variant="outline" onClick={() => setConfirming(true)}>
          {labels.history.delete}
        </Button>
      </div>
      <section className="flex flex-col gap-2">
        <h2>{labels.history.campaignTitle}</h2>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {inputs.map(([name, value]) => (
            <div key={name} className="flex gap-2">
              <dt className="text-muted-foreground">{fieldLabel(name)}:</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <PredictionResults result={result} />
      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title={labels.history.deleteTitle}
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm">{labels.history.deleteHint}</p>
          {remove.isError ? (
            <Alert variant="destructive" role="alert">
              {apiMessage(remove.error)}
            </Alert>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirming(false)}>
              {labels.history.cancel}
            </Button>
            <Button onClick={() => void confirmDelete()} disabled={remove.isPending}>
              {remove.isPending ? labels.history.deleting : labels.history.delete}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

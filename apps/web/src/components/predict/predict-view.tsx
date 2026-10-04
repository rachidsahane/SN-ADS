"use client";

import { PredictForm } from "@/components/predict/predict-form";
import { Alert } from "@/components/ui/alert";
import { useReferenceOptions } from "@/hooks/use-prediction";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

/** Page « Predict » : bandeau quand aucun modèle n'est actif, sinon le formulaire. */
export function PredictView() {
  const options = useReferenceOptions();
  if (options.isPending) {
    return (
      <p aria-busy="true" className="mt-4 text-sm text-muted-foreground">
        {labels.admin.users.loading}
      </p>
    );
  }
  if (options.isError) {
    return (
      <Alert variant="destructive" role="alert" className="mt-4">
        {apiMessage(options.error)}
      </Alert>
    );
  }
  if (options.data.model_version === null) {
    return (
      <Alert role="status" className="mt-4">
        {labels.model.noActive}
      </Alert>
    );
  }
  const optionalUsed = options.data.features_used.filter((field) =>
    ["advertising_platform", "advertising_tool"].includes(field),
  );
  return <PredictForm key={options.data.model_version.id} optionalUsed={optionalUsed} />;
}

"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PredictionResult } from "@/hooks/use-prediction";
import { useSavePrediction } from "@/hooks/use-predictions";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

const schema = z.object({
  name: z
    .string()
    .trim()
    .min(1, labels.history.save.nameInvalid)
    .max(100, labels.history.save.nameInvalid),
});
type Values = z.infer<typeof schema>;

/** Bouton « Save prediction » et sa fenêtre : le serveur recalcule les résultats à partir de la campagne. */
export function SavePrediction({ result }: { result: PredictionResult }) {
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button
          variant="outline"
          onClick={() => {
            setSaved(false);
            setOpen(true);
          }}
        >
          {labels.predict.save}
        </Button>
      </div>
      {saved ? (
        <Alert role="status" data-testid="saved-notice">
          {labels.history.save.done}
        </Alert>
      ) : null}
      <Dialog open={open} onClose={() => setOpen(false)} title={labels.history.save.title}>
        <SaveForm
          result={result}
          onClose={() => setOpen(false)}
          onSaved={() => {
            setSaved(true);
            setOpen(false);
          }}
        />
      </Dialog>
    </div>
  );
}

function SaveForm({
  result,
  onClose,
  onSaved,
}: {
  result: PredictionResult;
  onClose: () => void;
  onSaved: () => void;
}) {
  const id = useId();
  const save = useSavePrediction();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: labels.history.save.defaultName(
        result.input.campaign_channel,
        result.input.campaign_type,
      ),
    },
  });

  async function onSubmit(values: Values) {
    setFormError(null);
    try {
      await save.mutateAsync({ name: values.name, input: result.input });
    } catch (error) {
      setFormError(apiMessage(error));
      return;
    }
    onSaved();
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      {formError ? (
        <Alert variant="destructive" role="alert">
          {formError}
        </Alert>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${id}-name`}>{labels.history.save.name}</Label>
        <Input
          id={`${id}-name`}
          aria-invalid={errors.name ? true : undefined}
          aria-describedby={errors.name ? `${id}-name-error` : undefined}
          {...register("name")}
        />
        {errors.name ? (
          <p id={`${id}-name-error`} role="alert" className="text-sm text-destructive">
            {errors.name.message}
          </p>
        ) : null}
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose}>
          {labels.history.cancel}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? labels.history.save.submitting : labels.history.save.submit}
        </Button>
      </div>
    </form>
  );
}

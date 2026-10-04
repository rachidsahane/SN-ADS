"use client";

import { useId, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PredictionResult } from "@/hooks/use-prediction";
import { useSavePrediction } from "@/hooks/use-predictions";
import { apiMessage } from "@/lib/api/messages";
import { labels } from "@/lib/labels";

const MAX_NAME = 100;

type Props = {
  open: boolean;
  result: PredictionResult;
  onClose: () => void;
  onSaved: () => void;
};

/** Fenêtre « Save prediction » : nom facultatif (« Channel · Type » par défaut), le serveur recalcule les résultats. */
export function SavePredictionDialog({ open, result, onClose, onSaved }: Props) {
  return (
    <Dialog open={open} onClose={onClose} title={labels.history.save.title}>
      <SaveForm result={result} onClose={onClose} onSaved={onSaved} />
    </Dialog>
  );
}

function SaveForm({ result, onClose, onSaved }: Omit<Props, "open">) {
  const id = useId();
  const save = useSavePrediction();
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    const label =
      name.trim() ||
      labels.history.save.defaultName(result.input.campaign_channel, result.input.campaign_type);
    try {
      await save.mutateAsync({ name: label, input: result.input });
    } catch (error) {
      setFormError(apiMessage(error));
      return;
    }
    onSaved();
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-[10px]">
      {formError ? (
        <Alert variant="destructive" role="alert" className="!px-3 !py-2 !text-[13px]">
          {formError}
        </Alert>
      ) : null}
      <div className="field">
        <Label htmlFor={`${id}-name`}>{labels.history.save.name}</Label>
        <Input
          id={`${id}-name`}
          maxLength={MAX_NAME}
          value={name}
          placeholder={labels.history.save.placeholder}
          onChange={(event) => setName(event.target.value.slice(0, MAX_NAME))}
        />
        <div className="num mt-1 text-right text-[11px] text-neutral-700">
          {labels.history.save.counter(name.length)}
        </div>
      </div>
      <div className="dialog-actions">
        <Button variant="outline" onClick={onClose}>
          {labels.history.cancel}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? labels.history.save.submitting : labels.history.save.submit}
        </Button>
      </div>
    </form>
  );
}

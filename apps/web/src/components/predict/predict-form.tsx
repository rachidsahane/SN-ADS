"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { fieldLabel } from "@/components/model/active-model-view";
import { PredictionResults } from "@/components/predict/prediction-results";
import { SavePrediction } from "@/components/predict/save-prediction";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  type PredictionResult,
  fetchEngagementDefaults,
  useSimulate,
} from "@/hooks/use-prediction";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import {
  CAMPAIGN_TYPES,
  CHANNELS,
  ENGAGEMENT_FIELDS,
  GENDERS,
  OPTIONAL_FIELDS,
  type PredictValues,
  makePredictSchema,
} from "@/lib/schemas/prediction";

const DEFAULTS: PredictValues = {
  campaign_channel: "Email",
  campaign_type: "Conversion",
  ad_spend: 5000,
  age: 35,
  gender: "Female",
  income: 60000,
  previous_purchases: 2,
  loyalty_points: 1000,
  pages_per_visit: 5,
  time_on_site: 7,
  social_shares: 50,
  email_opens: 9,
  email_clicks: 4,
};

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3 border border-border p-4">
      <legend className="px-1 font-semibold">{title}</legend>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </fieldset>
  );
}

function FieldBox({
  id,
  name,
  error,
  children,
}: {
  id: string;
  name: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{fieldLabel(name)}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type Props = {
  /** Champs facultatifs que le modèle actif utilise (affichés et obligatoires). */
  optionalUsed: readonly string[];
};

/** Formulaire de campagne en trois blocs (PRD F-16), bouton « Predict », résultats dessous. */
export function PredictForm({ optionalUsed }: Props) {
  const ids = useId();
  const schema = useMemo(() => makePredictSchema(optionalUsed), [optionalUsed]);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const simulate = useSimulate();
  const form = useForm<PredictValues>({ resolver: zodResolver(schema), defaultValues: DEFAULTS });
  const { register, handleSubmit, getValues, setValue, setError, formState } = form;
  const errors = formState.errors;

  async function prefill(channel: string, campaignType: string) {
    try {
      const defaults = await fetchEngagementDefaults(channel, campaignType);
      for (const name of ENGAGEMENT_FIELDS) {
        setValue(name, defaults[name]);
      }
    } catch {
      // Les valeurs actuelles restent : l'utilisateur peut les saisir lui-même.
    }
  }

  useEffect(() => {
    void prefill(DEFAULTS.campaign_channel, DEFAULTS.campaign_type);
    // Une seule fois, à l'ouverture du formulaire.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(values: PredictValues) {
    setFormError(null);
    try {
      setResult(await simulate.mutateAsync(values));
    } catch (error) {
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        for (const detail of error.details) {
          if (detail.field && detail.field in DEFAULTS) {
            setError(detail.field as keyof PredictValues, {
              type: "server",
              message: detail.message,
            });
          }
        }
      }
      if (isUnexpectedError(error)) {
        reportError(error, {
          route: "predict-form",
          requestId: error instanceof ApiError ? error.requestId : null,
        });
      }
      setFormError(apiMessage(error));
    }
  }

  function apply(item: PredictionResult["recommendations"]["items"][number]) {
    setValue(item.lever as keyof PredictValues, item.to_value as never, { shouldValidate: true });
    void handleSubmit(onSubmit)();
  }

  function text(name: keyof PredictValues, type: "number" | "text", step?: string) {
    const id = `${ids}-${name}`;
    const error = errors[name]?.message;
    return (
      <FieldBox key={name} id={id} name={name} error={error}>
        <Input
          id={id}
          type={type}
          step={step}
          inputMode={type === "number" ? "decimal" : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          {...register(name, type === "number" ? { valueAsNumber: true } : {})}
        />
      </FieldBox>
    );
  }

  /** Changer le canal ou le type recharge les valeurs d'engagement (PRD US-11). */
  function select(
    name: "campaign_channel" | "campaign_type" | "gender",
    options: readonly string[],
  ) {
    const id = `${ids}-${name}`;
    const registered = register(name);
    const isPlan = name !== "gender";
    return (
      <FieldBox key={name} id={id} name={name} error={errors[name]?.message}>
        <Select
          id={id}
          {...registered}
          onChange={(event) => {
            void registered.onChange(event);
            if (isPlan) {
              const [channel, campaignType] =
                name === "campaign_channel"
                  ? [event.target.value, getValues("campaign_type")]
                  : [getValues("campaign_channel"), event.target.value];
              void prefill(channel, campaignType);
            }
          }}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </FieldBox>
    );
  }

  return (
    <div className="mt-4 flex flex-col gap-8">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
        {formError ? (
          <Alert variant="destructive" role="alert">
            {formError}
          </Alert>
        ) : null}
        <Block title={labels.predict.blocks.plan}>
          {select("campaign_channel", CHANNELS)}
          {select("campaign_type", CAMPAIGN_TYPES)}
          {text("ad_spend", "number", "any")}
        </Block>
        <Block title={labels.predict.blocks.audience}>
          {text("age", "number")}
          {select("gender", GENDERS)}
          {text("income", "number")}
          {text("previous_purchases", "number")}
          {text("loyalty_points", "number")}
          {OPTIONAL_FIELDS.filter((name) => optionalUsed.includes(name)).map((name) =>
            text(name, "text"),
          )}
        </Block>
        <Block title={labels.predict.blocks.engagement}>
          <p className="text-sm text-muted-foreground sm:col-span-2 lg:col-span-3">
            {labels.predict.engagementHint}
          </p>
          {text("pages_per_visit", "number", "any")}
          {text("time_on_site", "number", "any")}
          {text("social_shares", "number")}
          {text("email_opens", "number")}
          {text("email_clicks", "number")}
        </Block>
        <div>
          <Button type="submit" disabled={simulate.isPending}>
            {simulate.isPending ? labels.predict.submitting : labels.predict.submit}
          </Button>
        </div>
      </form>
      {result ? (
        <>
          <PredictionResults result={result} onApply={apply} busy={simulate.isPending} />
          <SavePrediction result={result} />
        </>
      ) : null}
    </div>
  );
}

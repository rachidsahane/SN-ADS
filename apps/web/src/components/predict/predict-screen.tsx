"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageShell } from "@/components/layout/page-shell";
import { PageTitle } from "@/components/layout/page-title";
import { PredictForm } from "@/components/predict/predict-form";
import { PredictionResults } from "@/components/predict/prediction-results";
import type { Recommendation } from "@/components/predict/recommendations-panel";
import { SavePredictionDialog } from "@/components/predict/save-prediction";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SpinnerIcon, WarningIcon } from "@/components/ui/icons";
import { Tag } from "@/components/ui/tag";
import {
  type PredictionResult,
  type ReferenceOptions,
  engagementDefaultsQuery,
  useSimulation,
} from "@/hooks/use-prediction";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { formatDateTime } from "@/lib/format";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { DEFAULT_FORM, type FormState, formFromInput, parseForm } from "@/lib/predict-form";
import { ENGAGEMENT_FIELDS, type PredictValues } from "@/lib/schemas/prediction";
import { useToast } from "@/providers/toast-provider";

/** Délai entre la dernière frappe et le recalcul (prototype : 400 ms). */
export const DEBOUNCE_MS = 400;

type Props = {
  options: ReferenceOptions;
  /** Prédiction enregistrée à afficher telle quelle (lecture seule) jusqu'à la première modification. */
  saved?: PredictionResult | null;
};

function ResultsPlaceholder({ children }: { children: string }) {
  return (
    <div className="blueprint px-6 py-12 text-center text-sm text-neutral-700">{children}</div>
  );
}

/**
 * Écran « Predict » du prototype : formulaire en trois blocs à gauche, résultats à droite, recalculés 400 ms après la
 * dernière frappe (aucun bouton « Predict »). Réutilisé en lecture seule pour une prédiction de l'historique.
 */
export function PredictScreen({ options, saved = null }: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const model = options.model_version;
  const hasModel = model !== null;
  const optionalUsed = useMemo(
    () =>
      options.features_used.filter((f) => ["advertising_platform", "advertising_tool"].includes(f)),
    [options.features_used],
  );
  const ranges = options.training_ranges;

  const [form, setForm] = useState<FormState>(() =>
    saved ? formFromInput(saved.input) : DEFAULT_FORM,
  );
  const [committed, setCommitted] = useState<PredictValues | null>(null);
  const [viewing, setViewing] = useState(saved !== null);
  const [saveOpen, setSaveOpen] = useState(false);
  const formRef = useRef(form);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const parsed = useMemo(() => parseForm(form, optionalUsed, ranges), [form, optionalUsed, ranges]);
  const sim = useSimulation(model?.id ?? "none", committed, hasModel && !viewing);

  function commit(next: FormState, immediate: boolean) {
    if (timer.current) {
      clearTimeout(timer.current);
    }
    const values = parseForm(next, optionalUsed, ranges).values;
    if (values === null || immediate) {
      setCommitted(values);
      return;
    }
    timer.current = setTimeout(() => setCommitted(values), DEBOUNCE_MS);
  }

  function update(patch: FormState, immediate = false) {
    const next = { ...formRef.current, ...patch };
    formRef.current = next;
    setForm(next);
    setViewing(false);
    commit(next, immediate);
  }

  async function prefill(channel: string, campaignType: string, immediate: boolean) {
    try {
      const defaults = await queryClient.fetchQuery(engagementDefaultsQuery(channel, campaignType));
      const current = formRef.current;
      if (current.campaign_channel !== channel || current.campaign_type !== campaignType) {
        return; // le choix a encore changé entre-temps
      }
      const patch: FormState = {};
      for (const name of ENGAGEMENT_FIELDS) {
        patch[name] = String(defaults[name]);
      }
      update(patch, immediate);
    } catch {
      // Les valeurs actuelles restent : l'utilisateur peut les saisir lui-même.
      if (immediate) {
        commit(formRef.current, true);
      }
    }
  }

  useEffect(() => {
    if (!hasModel || saved) {
      return;
    }
    // Ouverture : moyennes observées pour le canal et le type de départ, puis un seul premier calcul.
    void prefill(DEFAULT_FORM.campaign_channel ?? "", DEFAULT_FORM.campaign_type ?? "", true);
    return () => {
      if (timer.current) {
        clearTimeout(timer.current);
      }
    };
    // Une seule fois, à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onChange(name: string, value: string) {
    update({ [name]: value });
    if (name === "campaign_channel" || name === "campaign_type") {
      const next = { ...formRef.current };
      void prefill(next.campaign_channel ?? "", next.campaign_type ?? "", false);
    }
  }

  function onReset() {
    const current = formRef.current;
    void prefill(current.campaign_channel ?? "", current.campaign_type ?? "", false);
  }

  function onApply(item: Recommendation) {
    update({ [item.lever]: String(item.to_value ?? "") }, true);
  }

  const key = parsed.values ? JSON.stringify(parsed.values) : null;
  const committedKey = committed ? JSON.stringify(committed) : null;
  const waiting = hasModel && !viewing && key !== null && key !== committedKey;
  const pending = waiting || (hasModel && !viewing && sim.isFetching);

  const error = !viewing && committed !== null && sim.isError ? sim.error : null;
  useEffect(() => {
    if (error && isUnexpectedError(error)) {
      reportError(error, {
        route: "predict",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  // Le dernier résultat reste affiché pendant le recalcul ; un formulaire invalide le masque.
  const lastResult = useRef<PredictionResult | null>(saved);
  const fresh = viewing ? saved : parsed.values ? (sim.data ?? null) : null;
  if (fresh) {
    lastResult.current = fresh;
  }
  const result: PredictionResult | null =
    !hasModel || (!viewing && parsed.values === null) ? null : (fresh ?? lastResult.current);
  const modelVersion = result?.model_version.version ?? model?.version ?? null;

  return (
    <PageShell wide>
      <PageTitle
        subtitle={labels.predict.subtitle}
        actions={
          <>
            {pending ? (
              <div
                className="flex items-center gap-1.5 text-xs text-neutral-700"
                aria-live="polite"
              >
                <SpinnerIcon />
                {labels.predict.recalculating}
              </div>
            ) : null}
            {hasModel && modelVersion !== null ? (
              <Tag tone="accent" data-testid="model-tag">
                {labels.predict.modelTag(modelVersion)}
              </Tag>
            ) : null}
            <Button
              blueprint
              disabled={!result || !hasModel || viewing || error !== null}
              onClick={() => setSaveOpen(true)}
            >
              {labels.predict.save}
            </Button>
          </>
        }
      >
        {labels.predict.title}
      </PageTitle>

      {!hasModel ? (
        <div role="status" className="notice">
          <WarningIcon className="mt-px flex-none" />
          {labels.model.noActive}
        </div>
      ) : null}
      {viewing && saved ? (
        <div
          data-testid="viewing-bar"
          className="flex flex-wrap items-center justify-between gap-2.5 border border-divider px-[14px] py-2.5 text-sm"
        >
          <div>
            {labels.predict.viewing.intro} <strong className="font-medium">“{saved.label}”</strong>{" "}
            {labels.predict.viewing.detail(
              saved.created_at ? formatDateTime(saved.created_at) : "",
              `v${saved.model_version.version}`,
            )}
          </div>
          <Link href="/history" className="btn btn-ghost">
            {labels.predict.viewing.back}
          </Link>
        </div>
      ) : null}

      <div className="flex flex-wrap items-start gap-7">
        <PredictForm
          form={form}
          errors={parsed.errors}
          outOfRange={parsed.outOfRange}
          disabled={!hasModel}
          optionalUsed={optionalUsed}
          onChange={onChange}
          onReset={onReset}
        />
        <section
          aria-label={labels.predict.resultsLabel}
          aria-busy={pending}
          className="flex min-w-0 flex-[2_1_520px] flex-col gap-[22px]"
        >
          {hasModel && error ? (
            <Alert variant="destructive" role="alert">
              {apiMessage(error)}
            </Alert>
          ) : null}
          {hasModel && !result && !error ? (
            <ResultsPlaceholder>
              {parsed.values ? labels.predict.calculating : labels.predict.fixFields}
            </ResultsPlaceholder>
          ) : null}
          {result ? <PredictionResults result={result} onApply={onApply} /> : null}
        </section>
      </div>

      {result ? (
        <SavePredictionDialog
          open={saveOpen}
          result={result}
          onClose={() => setSaveOpen(false)}
          onSaved={() => {
            setSaveOpen(false);
            toast(labels.history.save.done);
          }}
        />
      ) : null}
    </PageShell>
  );
}

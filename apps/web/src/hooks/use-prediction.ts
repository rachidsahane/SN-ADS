"use client";

import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";
import { type PredictValues, toRequestBody } from "@/lib/schemas/prediction";

export type ReferenceOptions = components["schemas"]["ReferenceOptions"];
export type EngagementDefaults = components["schemas"]["EngagementDefaults"];
export type PredictionResult = components["schemas"]["PredictionResult"];

/** Description du formulaire selon le modèle actif (`model_version` vide : aucun modèle actif). Valable 1 minute. */
export function useReferenceOptions() {
  return useQuery({
    queryKey: queryKeys.referenceOptions(),
    queryFn: ({ signal }) => apiFetch<ReferenceOptions>("/api/v1/reference/options", { signal }),
    staleTime: 60_000,
  });
}

/** Moyennes observées de l'engagement pour un canal et un type (mises en cache : un seul appel par couple). */
export function engagementDefaultsQuery(channel: string, campaignType: string) {
  return queryOptions({
    queryKey: queryKeys.engagementDefaults(channel, campaignType),
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ campaign_channel: channel, campaign_type: campaignType });
      return apiFetch<EngagementDefaults>(
        `/api/v1/reference/engagement-defaults?${query.toString()}`,
        { signal },
      );
    },
    staleTime: 5 * 60_000,
  });
}

/**
 * Simulation d'une campagne (POST /api/v1/predictions/simulate), rien n'est enregistré. Le résultat précédent reste
 * affiché pendant le recalcul ; `enabled` coupe les appels (formulaire invalide, prédiction enregistrée affichée).
 */
export function useSimulation(modelId: string, values: PredictValues | null, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.simulation(modelId, values),
    queryFn: ({ signal }) =>
      apiFetch<PredictionResult>("/api/v1/predictions/simulate", {
        method: "POST",
        body: toRequestBody(values as PredictValues),
        signal,
      }),
    enabled: enabled && values !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: false,
  });
}

"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";
import { type PredictValues, toRequestBody } from "@/lib/schemas/prediction";

export type ReferenceOptions = components["schemas"]["ReferenceOptions"];
export type EngagementDefaults = components["schemas"]["EngagementDefaults"];
export type PredictionResult = components["schemas"]["PredictionResult"];

/** Description du formulaire selon le modèle actif (`model_version` vide : aucun modèle actif). */
export function useReferenceOptions() {
  return useQuery({
    queryKey: queryKeys.referenceOptions(),
    queryFn: ({ signal }) => apiFetch<ReferenceOptions>("/api/v1/reference/options", { signal }),
    staleTime: 0,
  });
}

export function fetchEngagementDefaults(channel: string, campaignType: string) {
  const query = new URLSearchParams({ campaign_channel: channel, campaign_type: campaignType });
  return apiFetch<EngagementDefaults>(`/api/v1/reference/engagement-defaults?${query.toString()}`);
}

/** Simulation d'une campagne (POST /api/v1/predictions/simulate) : un résultat par appel, rien n'est enregistré. */
export function useSimulate() {
  return useMutation({
    mutationFn: (values: PredictValues) =>
      apiFetch<PredictionResult>("/api/v1/predictions/simulate", {
        method: "POST",
        body: toRequestBody(values),
      }),
  });
}

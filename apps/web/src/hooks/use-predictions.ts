"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { PredictionResult } from "@/hooks/use-prediction";
import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type PredictionSummary = components["schemas"]["PredictionSummary"];
export type PredictionList = components["schemas"]["PredictionList"];
export type CampaignInput = components["schemas"]["CampaignInput"];

/** Les 50 dernières prédictions de l'utilisateur. */
export function usePredictionList() {
  return useQuery({
    queryKey: queryKeys.predictions(),
    queryFn: ({ signal }) => apiFetch<PredictionList>("/api/v1/predictions", { signal }),
    staleTime: 0,
  });
}

/** Une prédiction enregistrée (résultats figés) ; 404 si elle appartient à un autre. */
export function usePrediction(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.prediction(id),
    queryFn: ({ signal }) => apiFetch<PredictionResult>(`/api/v1/predictions/${id}`, { signal }),
    enabled,
    staleTime: 0,
    retry: false,
  });
}

/** Enregistrement : seuls le nom et la campagne partent, le serveur recalcule les résultats. */
export function useSavePrediction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; input: CampaignInput }) =>
      apiFetch<PredictionResult>("/api/v1/predictions", { method: "POST", body }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.predictions(), exact: true }),
  });
}

export function useDeletePrediction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/api/v1/predictions/${id}`, { method: "DELETE" }),
    // Only the list: refetching the (now deleted) prediction would be a 404 in the console.
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.predictions(), exact: true }),
  });
}

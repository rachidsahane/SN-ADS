"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type ModelVersion = components["schemas"]["ModelVersion"];
export type ModelVersionDetail = components["schemas"]["ModelVersionDetail"];
export type ModelVersionList = components["schemas"]["ModelVersionList"];

export const POLL_INTERVAL_MS = 3000;

export function isInProgress(status: ModelVersion["status"] | undefined): boolean {
  return status === "queued" || status === "running";
}

/** Liste des versions ; elle se recharge toutes les 3 secondes tant qu'un apprentissage est en cours. */
export function useModelVersions() {
  return useQuery({
    queryKey: queryKeys.adminModels(),
    queryFn: ({ signal }) => apiFetch<ModelVersionList>("/api/v1/admin/model-versions", { signal }),
    staleTime: 0,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => isInProgress(item.status)) ? POLL_INTERVAL_MS : false,
  });
}

/** Une version ; même rythme de rechargement tant qu'elle est en file ou en cours. */
export function useModelVersion(id: string) {
  return useQuery({
    queryKey: queryKeys.adminModel(id),
    queryFn: ({ signal }) =>
      apiFetch<ModelVersionDetail>(`/api/v1/admin/model-versions/${id}`, { signal }),
    staleTime: 0,
    refetchInterval: (query) => (isInProgress(query.state.data?.status) ? POLL_INTERVAL_MS : false),
  });
}

export type DataScope = ModelVersion["data_scope"];

/** Lancement d'un apprentissage (POST /api/v1/admin/model-versions) sur toutes les données ou celles de l'agence. */
export function useTrainModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dataScope: DataScope = "all") =>
      apiFetch<ModelVersionDetail>("/api/v1/admin/model-versions", {
        method: "POST",
        body: { data_scope: dataScope },
      }),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.adminModels() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.adminAudit() }),
      ]),
  });
}

/** Activation d'une version (POST .../activate) : la version active et le journal changent. */
export function useActivateModel(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<ModelVersionDetail>(`/api/v1/admin/model-versions/${id}/activate`, {
        method: "POST",
      }),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.adminModels() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.activeModel() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.referenceOptions() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.adminAudit() }),
      ]),
  });
}

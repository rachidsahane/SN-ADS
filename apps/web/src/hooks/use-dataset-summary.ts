"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type DatasetSummary = components["schemas"]["DatasetSummary"];

/** Résumé des données (GET /api/v1/admin/dataset/summary), mis en cache 30 s. */
export function useDatasetSummary() {
  return useQuery({
    queryKey: queryKeys.adminDataset(),
    queryFn: ({ signal }) => apiFetch<DatasetSummary>("/api/v1/admin/dataset/summary", { signal }),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

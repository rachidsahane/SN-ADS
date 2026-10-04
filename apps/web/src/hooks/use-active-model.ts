"use client";

import { useQuery } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type ActiveModel = components["schemas"]["ActiveModel"];

/** Modèle actif (GET /api/v1/model/active) ; `null` quand aucun n'est activé (409 NO_ACTIVE_MODEL). */
export function useActiveModel() {
  return useQuery({
    queryKey: queryKeys.activeModel(),
    queryFn: async ({ signal }) => {
      try {
        return await apiFetch<ActiveModel>("/api/v1/model/active", { signal });
      } catch (error) {
        if (error instanceof ApiError && error.code === "NO_ACTIVE_MODEL") {
          return null;
        }
        throw error;
      }
    },
    staleTime: 0,
  });
}

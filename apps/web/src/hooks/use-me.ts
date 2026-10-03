"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type MeResponse = components["schemas"]["MeResponse"];

/** Profil de l'utilisateur connecté (GET /api/v1/me). Les 401 et 403 de session sont traités par `apiFetch`. */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me(),
    queryFn: ({ signal }) => apiFetch<MeResponse>("/api/v1/me", { signal }),
    staleTime: 30_000,
    retry: false,
  });
}

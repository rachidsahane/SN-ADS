"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

type HealthResponse = components["schemas"]["HealthResponse"];

export type ApiHealthState = "checking" | "healthy" | "unreachable";

export const HEALTH_POLL_INTERVAL_MS = 5_000;
export const HEALTH_TIMEOUT_MS = 3_000;

/**
 * État de l'API, interrogé toutes les 5 s sur /api/health (même origine).
 * "unreachable" = échec réseau, réponse non 2xx (ex. 500 du proxy quand `api` est arrêté)
 * ou corps inattendu.
 */
export function useApiHealth(): { state: ApiHealthState; release: string | null } {
  const query = useQuery({
    queryKey: queryKeys.health(),
    queryFn: ({ signal }) =>
      apiFetch<HealthResponse>("/api/health", { signal, timeoutMs: HEALTH_TIMEOUT_MS }),
    refetchInterval: HEALTH_POLL_INTERVAL_MS,
    retry: false,
    staleTime: 0,
  });

  if (query.isError) {
    return { state: "unreachable", release: null };
  }
  if (query.isSuccess) {
    return query.data.status === "ok"
      ? { state: "healthy", release: query.data.release }
      : { state: "unreachable", release: null };
  }
  return { state: "checking", release: null };
}

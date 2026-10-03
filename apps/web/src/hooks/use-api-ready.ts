"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

type ReadyResponse = components["schemas"]["ReadyResponse"];

export type ApiReadyState = "checking" | "connected" | "unreachable";

export const READY_POLL_INTERVAL_MS = 5_000;
export const READY_TIMEOUT_MS = 3_000;

/**
 * État de la base de données, interrogé toutes les 5 s sur /api/ready (même origine).
 * "connected" seulement si l'API répond prête, base "ok" et numéro de schéma non vide.
 * "unreachable" = échec réseau, 503 (corps "not_ready"), réponse non 2xx ou corps inattendu.
 */
export function useApiReady(): { state: ApiReadyState; schemaVersion: string | null } {
  const query = useQuery({
    queryKey: queryKeys.ready(),
    queryFn: ({ signal }) =>
      apiFetch<ReadyResponse>("/api/ready", { signal, timeoutMs: READY_TIMEOUT_MS }),
    refetchInterval: READY_POLL_INTERVAL_MS,
    retry: false,
    staleTime: 0,
  });

  if (query.isError) {
    return { state: "unreachable", schemaVersion: null };
  }
  if (query.isSuccess) {
    // Le corps vient du réseau : on ne fait pas confiance à sa forme au-delà des types générés.
    const data = query.data as Partial<ReadyResponse> | null;
    const schemaVersion = data?.schema_version;
    if (
      data?.status === "ready" &&
      data.checks?.database === "ok" &&
      typeof schemaVersion === "string" &&
      schemaVersion !== ""
    ) {
      return { state: "connected", schemaVersion };
    }
    return { state: "unreachable", schemaVersion: null };
  }
  return { state: "checking", schemaVersion: null };
}

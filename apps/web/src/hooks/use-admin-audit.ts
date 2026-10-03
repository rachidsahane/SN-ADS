"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type AuditEntry = components["schemas"]["AuditEntry"];
export type AuditLogPage = components["schemas"]["AuditLogPage"];

const PAGE_SIZE = 50;

/** Journal d'audit paginé (GET /api/v1/admin/audit-log) : toujours rechargé à l'ouverture de la page. */
export function useAdminAudit() {
  return useInfiniteQuery({
    queryKey: queryKeys.adminAudit(),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => {
      const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (pageParam !== null) {
        query.set("cursor", pageParam);
      }
      return apiFetch<AuditLogPage>(`/api/v1/admin/audit-log?${query.toString()}`, { signal });
    },
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    staleTime: 0,
    refetchOnMount: "always",
  });
}

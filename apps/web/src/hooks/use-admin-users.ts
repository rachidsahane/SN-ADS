"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type AdminUser = components["schemas"]["AdminUser"];
export type AdminUserPage = components["schemas"]["AdminUserPage"];
export type InviteUserBody = components["schemas"]["InviteUserRequest"];
export type UpdateUserBody = components["schemas"]["UpdateUserRequest"];

const PAGE_SIZE = 50;

/** Liste paginée des utilisateurs (GET /api/v1/admin/users), curseur renvoyé par l'API. */
export function useAdminUsers() {
  return useInfiniteQuery({
    queryKey: queryKeys.adminUsers(),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => {
      const query = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (pageParam !== null) {
        query.set("cursor", pageParam);
      }
      return apiFetch<AdminUserPage>(`/api/v1/admin/users?${query.toString()}`, { signal });
    },
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
}

/**
 * Une action sur les utilisateurs change aussi le journal d'audit : les deux listes sont invalidées.
 * La promesse est renvoyée pour que la mutation reste « en cours » jusqu'au rechargement de la liste.
 */
function useInvalidateAdminLists() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.adminAudit() }),
    ]);
}

/**
 * Invitation d'un utilisateur (POST /api/v1/admin/users/invite). Le rechargement des listes n'est pas
 * attendu : la fenêtre se ferme dès que l'invitation est envoyée, la nouvelle ligne apparaît ensuite.
 */
export function useInviteUser() {
  const invalidate = useInvalidateAdminLists();
  return useMutation({
    mutationFn: (body: InviteUserBody) =>
      apiFetch<AdminUser>("/api/v1/admin/users/invite", { method: "POST", body }),
    onSuccess: () => {
      void invalidate();
    },
  });
}

/** Changement de rôle ou d'activité (PATCH /api/v1/admin/users/{id}), corps limité aux clés modifiées. */
export function useUpdateUser() {
  const invalidate = useInvalidateAdminLists();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateUserBody }) =>
      apiFetch<AdminUser>(`/api/v1/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: invalidate,
  });
}

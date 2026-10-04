"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";
import type { components } from "@/lib/api/types.gen";

export type DatasetUploadResult = components["schemas"]["DatasetUploadResult"];

/** Les 60 secondes laissent le temps à l'API de contrôler et d'insérer un gros fichier. */
const UPLOAD_TIMEOUT_MS = 60_000;

/** Import d'un fichier de l'agence (POST /api/v1/admin/dataset/upload) : totaux et journal d'audit à recharger. */
export function useUploadDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch<DatasetUploadResult>("/api/v1/admin/dataset/upload", {
        method: "POST",
        formData,
        timeoutMs: UPLOAD_TIMEOUT_MS,
      });
    },
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.adminDataset() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.adminAudit() }),
      ]),
  });
}

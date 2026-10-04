"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { PageShell } from "@/components/layout/page-shell";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

/**
 * Garde de l'espace d'administration (D-087) : les pages enfants ne s'affichent, et ne lancent donc
 * aucune requête d'administration, qu'une fois le rôle connu. L'API reste la vraie barrière (403).
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data: me, error, isPending } = useMe();
  const role = me?.role;
  // 401 et 403 de session sont déjà traités par `apiFetch` (retour à Sign in) : ce ne sont pas des erreurs inattendues.
  const handled = error instanceof ApiError && (error.status === 401 || error.status === 403);

  useEffect(() => {
    if (role !== undefined && role !== "admin") {
      router.replace("/predict?notice=forbidden");
    }
  }, [role, router]);

  useEffect(() => {
    if (error && !handled) {
      reportError(error, {
        route: "admin-layout",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error, handled]);

  if (isPending || handled) {
    // Le rôle n'est pas encore connu : on réserve la place de la page (aucun texte, aucune requête d'administration).
    return (
      <PageShell>
        <div aria-busy="true" className="flex flex-col gap-[22px]">
          <Skeleton className="h-[58px] w-64" />
          <Skeleton className="h-[72px]" />
          <Skeleton className="h-[260px]" />
        </div>
      </PageShell>
    );
  }
  if (error) {
    return (
      <PageShell>
        <Alert variant="destructive" role="alert">
          {labels.errors.serviceUnavailable}
        </Alert>
      </PageShell>
    );
  }
  if (role !== "admin") {
    return null;
  }
  return <>{children}</>;
}

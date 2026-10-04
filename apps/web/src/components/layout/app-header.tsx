"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppNav } from "@/components/layout/app-nav";
import { Button } from "@/components/ui/button";
import { LogOutIcon } from "@/components/ui/icons";
import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { getBrowserSupabase } from "@/lib/supabase/browser";

/** En-tête de l'application : nom de l'outil, menu, nom et rôle de l'utilisateur (jamais son e-mail) et « Sign out ». */
export function AppHeader() {
  const queryClient = useQueryClient();
  const { data: me, error, isPending } = useMe();
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    // 401 et 403 de session sont déjà traités (déconnexion et retour à Sign in) : ce ne sont pas des erreurs inattendues.
    if (error && !(error instanceof ApiError && (error.status === 401 || error.status === 403))) {
      reportError(error, {
        route: "app-header",
        requestId: error instanceof ApiError ? error.requestId : null,
      });
    }
  }, [error]);

  async function signOut() {
    setSigningOut(true);
    try {
      await getBrowserSupabase().auth.signOut({ scope: "local" });
    } catch {
      // Même si l'appel échoue, on quitte l'espace connecté.
    }
    queryClient.clear();
    // Rechargement complet : plus aucun état ni cache de l'utilisateur précédent, et pas de course avec une
    // actualisation de la page pendant que la session disparaît.
    window.location.assign("/login");
  }

  return (
    <header className="flex min-h-14 flex-wrap items-center gap-5 border-b border-divider px-6">
      <Link
        href="/"
        className="whitespace-nowrap font-heading text-[22px] font-semibold tracking-[0.06em] text-foreground no-underline hover:text-foreground"
      >
        {labels.app.wordmark}
      </Link>
      <AppNav />
      <div className="ml-auto flex items-center gap-2.5 md:ml-0">
        {isPending ? (
          <div className="flex flex-col items-end gap-1" aria-busy="true">
            <span className="skeleton block h-3.5 w-24" />
            <span className="skeleton block h-2.5 w-16" />
          </div>
        ) : me ? (
          <div className="text-right leading-[1.2]">
            <div data-testid="user-name" className="max-w-[40vw] truncate text-[13px] font-medium">
              {me.full_name}
            </div>
            <div data-testid="user-role" className="text-[11px] text-neutral-700">
              {me.role === "admin"
                ? labels.admin.users.roleLabels.admin
                : labels.admin.users.roleLabels.marketer}
            </div>
          </div>
        ) : null}
        <Button variant="outline" onClick={signOut} disabled={signingOut}>
          <LogOutIcon />
          {labels.auth.signOut}
        </Button>
      </div>
    </header>
  );
}

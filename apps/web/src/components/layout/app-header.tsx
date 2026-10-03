"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppNav } from "@/components/layout/app-nav";
import { Button } from "@/components/ui/button";
import { useMe } from "@/hooks/use-me";
import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { getBrowserSupabase } from "@/lib/supabase/browser";

/** En-tête de l'application : nom de l'outil, nom de l'utilisateur (jamais son e-mail) et « Sign out ». */
export function AppHeader() {
  const router = useRouter();
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
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex w-full max-w-[1440px] flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-3">
        <Link
          href="/"
          className="whitespace-nowrap font-heading text-[22px] font-semibold tracking-[0.06em] text-foreground no-underline hover:text-foreground"
        >
          {labels.app.wordmark}
        </Link>
        <AppNav />
        <div className="flex items-center gap-4">
          {isPending ? (
            <span aria-busy="true" className="block h-4 w-28 animate-pulse bg-neutral-200" />
          ) : me ? (
            <span
              data-testid="user-name"
              className="max-w-[40vw] truncate text-sm font-medium sm:max-w-none"
            >
              {me.full_name}
            </span>
          ) : null}
          <Button variant="outline" size="sm" onClick={signOut} disabled={signingOut}>
            {labels.auth.signOut}
          </Button>
        </div>
      </div>
    </header>
  );
}

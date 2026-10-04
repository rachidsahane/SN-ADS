"use client";

import { useEffect } from "react";

import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";

/** Erreur inattendue dans une page de l'espace connecté : message simple et « Try again », jamais de trace technique. */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportError(error, { page: "app-error", digest: error.digest });
  }, [error]);

  return (
    <PageShell>
      <section className="blueprint flex flex-col gap-3 p-6">
        <h1 className="m-0 text-[32px]">{labels.errors.generic}</h1>
        <p className="text-sm text-neutral-700">{labels.errors.genericHint}</p>
        {error.digest ? (
          <p className="text-xs text-neutral-700">{labels.errors.reference(error.digest)}</p>
        ) : null}
        <Button blueprint className="self-start" onClick={reset}>
          {labels.errors.tryAgain}
        </Button>
      </section>
    </PageShell>
  );
}

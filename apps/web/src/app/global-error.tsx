"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/observability";
import { labels } from "@/lib/labels";

import "./globals.css";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportError(error, { page: "global-error", digest: error.digest });
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col justify-center gap-3 px-6">
          <h1>{labels.errors.generic}</h1>
          <p className="text-neutral-700">{labels.errors.genericHint}</p>
          {error.digest ? (
            <p className="text-sm text-neutral-700">{labels.errors.reference(error.digest)}</p>
          ) : null}
          <button type="button" className="self-start underline" onClick={reset}>
            {labels.errors.tryAgain}
          </button>
        </main>
      </body>
    </html>
  );
}

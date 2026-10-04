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
        <main className="flex min-h-screen items-center justify-center p-6">
          <div className="flex w-full max-w-[400px] flex-col gap-5">
            <div className="font-heading text-[28px] font-semibold tracking-[0.06em]">
              {labels.app.wordmark}
            </div>
            <section className="blueprint flex flex-col gap-[14px] p-6">
              <h1 className="m-0 text-[32px]">{labels.errors.generic}</h1>
              <p className="text-sm text-neutral-700">{labels.errors.genericHint}</p>
              {error.digest ? (
                <p className="text-xs text-neutral-700">{labels.errors.reference(error.digest)}</p>
              ) : null}
              <button type="button" className="btn btn-primary self-start" onClick={reset}>
                {labels.errors.tryAgain}
              </button>
            </section>
          </div>
        </main>
      </body>
    </html>
  );
}

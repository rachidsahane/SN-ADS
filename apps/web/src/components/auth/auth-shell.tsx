import type { ReactNode } from "react";

import { labels } from "@/lib/labels";

/** Cadre centré des écrans publics (prototype) : nom de l'outil, carte « blueprint » avec le titre (`<h1>`), mention d'invitation. */
export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="flex w-full max-w-[400px] flex-col gap-5">
        <div className="flex items-baseline justify-between">
          <div className="font-heading text-[28px] font-semibold tracking-[0.06em]">
            {labels.app.wordmark}
          </div>
          <div className="text-xs text-neutral-700">{labels.app.internal}</div>
        </div>
        <section className="blueprint flex flex-col gap-[14px] p-6">
          <h1 className="m-0 text-[32px]">{title}</h1>
          {children}
        </section>
        <div className="text-xs text-neutral-700">{labels.auth.invitationFootnote}</div>
      </div>
    </main>
  );
}

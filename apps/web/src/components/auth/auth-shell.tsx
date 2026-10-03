import type { ReactNode } from "react";

import { labels } from "@/lib/labels";

/** Cadre centré des écrans publics : nom de l'outil, titre de la page (`<h1>`) puis le formulaire. */
export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-10">
      <div className="mb-6 font-heading text-[22px] font-semibold tracking-[0.06em]">
        {labels.app.wordmark}
      </div>
      <section className="blueprint flex flex-col gap-5 p-6">
        <h1 className="text-[34px]">{title}</h1>
        {children}
      </section>
    </main>
  );
}

import { ApiStatus } from "@/components/feedback/api-status";
import { DatabaseStatus } from "@/components/feedback/database-status";
import { labels } from "@/lib/labels";

/** Page d'accueil provisoire (phases 0 et 1) : titre, état de l'API et de la base. Remplacée à la phase 2. */
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col gap-5 px-6 py-6">
      <div className="font-heading text-[22px] font-semibold tracking-[0.06em]">
        {labels.app.wordmark}
      </div>
      <div>
        <h1 className="mb-1 text-[38px]">{labels.app.name}</h1>
        <p className="text-sm text-neutral-700">{labels.app.tagline}</p>
      </div>
      <section aria-label={labels.status.sectionTitle} className="blueprint max-w-md p-4">
        <p className="kicker mb-2">{labels.status.sectionTitle}</p>
        <div className="flex flex-col gap-2">
          <ApiStatus />
          <DatabaseStatus />
        </div>
      </section>
    </main>
  );
}

import { ApiStatus } from "@/components/feedback/api-status";
import { labels } from "@/lib/labels";

/** Page d'accueil provisoire de la phase 0 : titre et état de l'API. Remplacée à la phase 2. */
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
        <ApiStatus />
      </section>
    </main>
  );
}

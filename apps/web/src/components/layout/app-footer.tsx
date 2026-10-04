import { env } from "@/lib/env";
import { labels } from "@/lib/labels";

/** Pied de page du prototype : nom de l'agence à gauche, version à droite. */
export function AppFooter() {
  return (
    <footer className="mt-auto flex flex-wrap justify-between gap-3 border-t border-divider px-6 py-[14px] text-[11px] text-neutral-700">
      <span>{labels.app.footerLeft}</span>
      <span className="num">{labels.app.footerRelease(env.NEXT_PUBLIC_APP_RELEASE)}</span>
    </footer>
  );
}

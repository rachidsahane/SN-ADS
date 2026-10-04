import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Colonne de contenu d'une page (prototype) : 1 200 px de large partout, 1 440 px pour Predict ;
 * espacement 22 px entre les blocs (20 px sur Predict).
 */
export function PageShell({ wide = false, children }: { wide?: boolean; children: ReactNode }) {
  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col",
        wide ? "max-w-predict gap-5" : "max-w-page gap-[22px]",
      )}
    >
      {children}
    </div>
  );
}

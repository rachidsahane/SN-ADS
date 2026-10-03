import type { ReactNode } from "react";

/** Titre de page : le seul `<h1>` de chaque écran de l'application. */
export function PageTitle({ children }: { children: ReactNode }) {
  return <h1>{children}</h1>;
}

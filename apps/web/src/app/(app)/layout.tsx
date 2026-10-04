import type { ReactNode } from "react";

import { AppFooter } from "@/components/layout/app-footer";
import { AppHeader } from "@/components/layout/app-header";

/** Espace connecté : en-tête commun, contenu de la page, pied de page. La session est exigée par le middleware. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader />
      <main className="w-full flex-1 p-6">{children}</main>
      <AppFooter />
    </div>
  );
}

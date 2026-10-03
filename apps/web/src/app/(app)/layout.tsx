import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";

/** Espace connecté : en-tête commun, puis le contenu de la page. La session est exigée par le middleware. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto w-full max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  );
}

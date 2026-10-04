import type { ReactNode } from "react";

type PageTitleProps = {
  children: ReactNode;
  /** Phrase sous le titre (14 px, gris). */
  subtitle?: string;
  /** Action principale de la page, à droite du titre. */
  actions?: ReactNode;
};

/** Titre de page : le seul `<h1>` de chaque écran de l'application (prototype : 38 px, sous-titre, action à droite). */
export function PageTitle({ children, subtitle, actions }: PageTitleProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="m-0 text-[38px]">{children}</h1>
        {subtitle ? <div className="text-sm text-neutral-700">{subtitle}</div> : null}
      </div>
      {actions ? <div className="flex items-center gap-3">{actions}</div> : null}
    </div>
  );
}

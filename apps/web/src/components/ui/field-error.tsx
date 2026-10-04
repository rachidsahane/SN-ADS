import type { ReactNode } from "react";

import { ErrorIcon, WarningIcon } from "@/components/ui/icons";

/** Message d'erreur sous un champ : bleu foncé, 12 px, icône cercle (prototype). */
export function FieldError({
  id,
  children,
  alert = true,
}: {
  id?: string;
  children: ReactNode;
  /** `false` quand une autre alerte de la page doit rester la seule `role="alert"` (écrans de connexion). */
  alert?: boolean;
}) {
  return (
    <div
      id={id}
      role={alert ? "alert" : undefined}
      className="mt-1 flex items-start gap-1 text-xs font-medium text-brand-800"
    >
      <ErrorIcon className="mt-0.5 flex-none" />
      {children}
    </div>
  );
}

/** Avertissement sous un champ (hors des valeurs vues par le modèle) : italique, gris. */
export function FieldWarning({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <div
      id={id}
      data-testid="field-warning"
      className="mt-1 flex items-start gap-1 text-xs italic text-neutral-700"
    >
      <WarningIcon size={13} className="mt-0.5 flex-none" />
      {children}
    </div>
  );
}

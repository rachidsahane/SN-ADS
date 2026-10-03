"use client";

import { useApiHealth } from "@/hooks/use-api-health";
import { cn } from "@/lib/utils";
import { labels } from "@/lib/labels";

/** Ligne d'état de l'API de la page d'accueil provisoire (phase 0). */
export function ApiStatus() {
  const { state } = useApiHealth();
  return (
    <p
      role="status"
      aria-live="polite"
      data-testid="api-status"
      data-state={state}
      className={cn(
        "inline-flex items-center gap-2 text-base font-medium",
        state === "healthy" && "text-success",
        state === "unreachable" && "text-danger",
        state === "checking" && "text-neutral-700",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-2.5 rounded-full",
          state === "healthy" && "bg-success",
          state === "unreachable" && "bg-danger",
          state === "checking" && "bg-neutral-500",
        )}
      />
      {labels.status.api[state]}
    </p>
  );
}

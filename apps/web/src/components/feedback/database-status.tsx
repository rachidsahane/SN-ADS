"use client";

import { useApiReady } from "@/hooks/use-api-ready";
import { cn } from "@/lib/utils";
import { labels } from "@/lib/labels";

/** Ligne d'état de la base de données de la page d'accueil provisoire (phase 1). */
export function DatabaseStatus() {
  const { state, schemaVersion } = useApiReady();
  const text =
    state === "connected" && schemaVersion !== null
      ? labels.status.database.connected(schemaVersion)
      : state === "checking"
        ? labels.status.database.checking
        : labels.status.database.unreachable;
  return (
    <p
      role="status"
      aria-live="polite"
      data-testid="database-status"
      data-state={state}
      className={cn(
        "inline-flex items-center gap-2 text-base font-medium",
        state === "connected" && "text-success",
        state === "unreachable" && "text-danger",
        state === "checking" && "text-neutral-700",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-2.5 rounded-full",
          state === "connected" && "bg-success",
          state === "unreachable" && "bg-danger",
          state === "checking" && "bg-neutral-500",
        )}
      />
      {text}
    </p>
  );
}

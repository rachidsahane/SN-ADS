import type { Instrumentation } from "next";

import { reportError } from "@/lib/observability";

export function register(): void {
  // Sentry serveur : phase 16.
}

/** Toute erreur serveur non gérée passe par l'observabilité (CLAUDE.md, règle 8). */
export const onRequestError: Instrumentation.onRequestError = (error, request) => {
  reportError(error, { route: request.path, method: request.method });
};

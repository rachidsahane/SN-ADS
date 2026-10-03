import { ApiError } from "@/lib/api/client";
import { labels } from "@/lib/labels";

/** Texte à montrer pour une erreur d'appel : le message de l'API tel que reçu, sinon l'indisponibilité du service. */
export function apiMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : labels.errors.serviceUnavailable;
}

/** Une erreur est inattendue (à remonter) quand ce n'est pas un refus métier de l'API (statut 4xx). */
export function isUnexpectedError(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status >= 500;
}

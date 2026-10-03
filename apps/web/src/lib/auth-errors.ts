/** Forme minimale d'une erreur de supabase-js (`AuthError` et sous-classes) : seul ce que l'interface lit. */
export type AuthErrorLike = {
  name?: string;
  status?: number;
  code?: string;
};

/**
 * - `rate_limited` : trop de demandes (429, `over_*_rate_limit`) ;
 * - `unavailable` : réseau coupé, passerelle ou serveur en panne (aucune réponse exploitable) ;
 * - `disabled` : compte désactivé (code `user_banned` de gotrue, reconnu par son code et jamais par son statut) ;
 * - `rejected` : le serveur d'authentification a refusé la demande (4xx).
 */
export type AuthErrorKind = "rate_limited" | "unavailable" | "disabled" | "rejected";

export function classifyAuthError(error: AuthErrorLike): AuthErrorKind {
  if (error.code === "user_banned") {
    return "disabled";
  }
  if (error.status === 429 || error.code?.startsWith("over_") === true) {
    return "rate_limited";
  }
  if (
    error.name === "AuthRetryableFetchError" ||
    error.status === undefined ||
    error.status === 0 ||
    error.status >= 500
  ) {
    return "unavailable";
  }
  return "rejected";
}

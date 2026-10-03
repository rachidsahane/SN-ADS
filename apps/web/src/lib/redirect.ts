/**
 * Tout caractère hors ASCII imprimable sans espace : contrôles (dont tabulation et retour à la ligne, que les
 * navigateurs suppriment d'une URL), espace, et caractères non ASCII (un en-tête `Location` ne peut pas les porter :
 * la route /auth/confirm répondrait 500 après avoir consommé le jeton). Un chemin légitime arrive encodé en %XX.
 */
const UNSAFE_CHARACTERS = /[^\u0021-\u007e]/;

/**
 * Valide un chemin de redirection `?next=` (SECURITY_NOTES.md 4.4, SEC-17) : seul un chemin du site est accepté,
 * jamais une URL absolue, un schéma ou un chemin relatif au protocole. Sinon, retourne `fallback`.
 */
export function safeNextPath(next: string | null | undefined, fallback = "/predict"): string {
  if (typeof next !== "string" || !next.startsWith("/") || next.startsWith("//")) {
    return fallback;
  }
  if (next.includes("\\") || UNSAFE_CHARACTERS.test(next)) {
    return fallback;
  }
  try {
    const resolved = new URL(next, "http://placeholder.invalid");
    // `/.//evil.com` se normalise en `//evil.com` : refusé aussi, par prudence.
    if (resolved.origin !== "http://placeholder.invalid" || resolved.pathname.startsWith("//")) {
      return fallback;
    }
  } catch {
    return fallback;
  }
  return next;
}

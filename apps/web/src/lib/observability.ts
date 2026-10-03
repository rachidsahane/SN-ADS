import { env } from "@/lib/env";

/** Contexte joint à une erreur. Jamais d'e-mail, de jeton ni de valeur saisie (SECURITY_NOTES.md section 5). */
export type ErrorContext = {
  requestId?: string | null;
  page?: string;
  route?: string;
  userId?: string;
  [key: string]: string | number | boolean | null | undefined;
};

const SENSITIVE_KEY = /e-?mail|password|token|secret|authorization|cookie|key/i;

function sanitize(context: ErrorContext): Record<string, unknown> {
  const clean: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(context)) {
    if (value === undefined) {
      continue;
    }
    clean[key] = SENSITIVE_KEY.test(key) ? "[redacted]" : value;
  }
  return clean;
}

/**
 * Point unique de remontée des erreurs de l'interface.
 * Avant la phase 16 : journal JSON local (console.error). La phase 16 y branche Sentry
 * sans changer cette signature.
 */
export function reportError(error: unknown, context: ErrorContext = {}): void {
  const err = error instanceof Error ? error : new Error(String(error));
  console.error(
    JSON.stringify({
      level: "error",
      service: "web",
      environment: env.NEXT_PUBLIC_APP_ENV,
      release: env.NEXT_PUBLIC_APP_RELEASE,
      error: { name: err.name, message: err.message },
      ...sanitize(context),
    }),
  );
}

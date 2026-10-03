import { type ApiErrorDetail, parseApiErrorBody } from "@/lib/api/errors";
import { labels } from "@/lib/labels";
import { getBrowserSupabase } from "@/lib/supabase/browser";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: ApiErrorDetail[],
    public requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiFetchInit = {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  /** Délai maximal avant abandon de la requête (défaut 15 s). */
  timeoutMs?: number;
};

export const DEFAULT_TIMEOUT_MS = 15_000;

/**
 * Identifiant de requête (UUID v4). `crypto.randomUUID` n'existe qu'en contexte sécurisé
 * (HTTPS ou localhost) : sur http://web:3000 (tests dans Docker) ou une adresse réseau locale,
 * on retombe sur `getRandomValues`, disponible partout.
 */
export function newRequestId(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** Jeton d'accès de la session en cours, ou null (pas de session, ou stockage indisponible). */
async function currentAccessToken(): Promise<string | null> {
  try {
    const { data } = await getBrowserSupabase().auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}

/**
 * Session perdue ou compte désactivé : déconnexion locale puis retour à « Sign in ».
 * Le rafraîchissement unique du jeton et le message `session_expired` arrivent avec la phase 15.
 */
async function endSession(destination: string): Promise<void> {
  try {
    await getBrowserSupabase().auth.signOut({ scope: "local" });
  } catch {
    // Le stockage de session peut être indisponible : la redirection a lieu quand même.
  }
  window.location.assign(destination);
}

/**
 * Appel unique vers l'API, toujours sur la même origine (/api/...). Le jeton de la session est joint
 * (jamais pour une autre adresse) ; une session perdue ramène à /login. Rafraîchissement unique : phase 15.
 *
 * Le délai maximal passe par un AbortController maison : `AbortSignal.any` n'existe pas dans jsdom.
 */
export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": newRequestId(),
  };
  if (path.startsWith("/api/")) {
    const accessToken = await currentAccessToken();
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }
  }
  let body: BodyInit | undefined;
  if (init.formData) {
    body = init.formData;
  } else if (init.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }

  const controller = new AbortController();
  const abort = () => controller.abort();
  if (init.signal?.aborted) {
    abort();
  }
  init.signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, init.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(new URL(path, window.location.origin), {
      method: init.method ?? "GET",
      headers,
      body,
      signal: controller.signal,
    });

    if (!response.ok) {
      const parsed = parseApiErrorBody(await response.json().catch(() => null));
      const error = new ApiError(
        response.status,
        parsed?.code ?? "INTERNAL_ERROR",
        parsed?.message ?? labels.errors.serviceUnavailable,
        parsed?.details ?? [],
        parsed?.requestId ?? response.headers.get("X-Request-ID"),
      );
      if (
        error.status === 401 &&
        (error.code === "UNAUTHENTICATED" || error.code === "TOKEN_EXPIRED")
      ) {
        const here = `${window.location.pathname}${window.location.search}`;
        await endSession(`/login?next=${encodeURIComponent(here)}`);
      } else if (error.status === 403 && error.code === "ACCOUNT_DISABLED") {
        await endSession("/login?reason=disabled");
      }
      throw error;
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}

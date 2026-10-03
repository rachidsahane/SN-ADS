/** Élément de `error.details` (API_SPEC.md section 3). */
export type ApiErrorDetail = {
  field?: string;
  row?: number;
  column?: string;
  issue?: string;
  message?: string;
};

export type ApiErrorBody = {
  code: string;
  message: string;
  details: ApiErrorDetail[];
  requestId: string | null;
};

/** Lit le corps d'erreur standard ; renvoie null si le corps n'a pas ce format (ex. page 500 du proxy). */
export function parseApiErrorBody(payload: unknown): ApiErrorBody | null {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) {
    return null;
  }
  const error = (payload as { error: unknown }).error;
  if (typeof error !== "object" || error === null) {
    return null;
  }
  const { code, message, details, request_id } = error as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string") {
    return null;
  }
  return {
    code,
    message,
    details: Array.isArray(details) ? (details as ApiErrorDetail[]) : [],
    requestId: typeof request_id === "string" ? request_id : null,
  };
}

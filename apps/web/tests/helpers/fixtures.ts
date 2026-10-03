/** Profil renvoyé par GET /api/v1/me (API_SPEC.md 6.2). Valeurs factices. */
export function meFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "6b1f0c1e-5d0a-4f43-9c53-2f6a8d0c1111",
    email: "e2e-marketer-a@example.test",
    full_name: "E2E Marketer A",
    role: "marketer",
    is_active: true,
    ...overrides,
  };
}

/** Erreur de l'API au format standard (API_SPEC.md section 3). */
export function apiErrorBody(code: string, message = "Error.", requestId = "rid-test") {
  return { error: { code, message, details: [], request_id: requestId } };
}

/** Erreur du type renvoyé par supabase-js (`AuthError` et sous-classes), réduite à ce que l'interface lit. */
export function authError(init: {
  name?: string;
  status?: number;
  code?: string;
  message?: string;
}) {
  return {
    name: init.name ?? "AuthApiError",
    status: init.status,
    code: init.code,
    message: init.message ?? "auth error",
  };
}

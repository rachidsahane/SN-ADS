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

/** Identifiant de l'administrateur connecté dans les tests de la phase 3 (valeur factice). */
export const ADMIN_ID = "0a0a0a0a-0000-4000-8000-00000000000a";

/** Profil administrateur renvoyé par GET /api/v1/me. */
export function adminMeFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return meFixture({
    id: ADMIN_ID,
    email: "e2e-admin@example.test",
    full_name: "E2E Admin",
    role: "admin",
    ...overrides,
  });
}

/** Objet `AdminUser` de API_SPEC.md 6.6 : exactement sept champs. */
export function adminUserFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    email: "ada@example.test",
    full_name: "Ada Lovelace",
    role: "marketer",
    is_active: true,
    status: "active",
    created_at: "2026-10-01T09:30:00.123456+00:00",
    ...overrides,
  };
}

/** Page de GET /api/v1/admin/users : `{ items, next_cursor }` (D-081). */
export function adminUsersPage(items: unknown[], nextCursor: string | null = null) {
  return { items, next_cursor: nextCursor };
}

/** Entrée de GET /api/v1/admin/audit-log (API_SPEC.md 6.9). */
export function auditEntryFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1,
    created_at: "2026-10-03T14:05:00.123456+00:00",
    actor: { id: ADMIN_ID, full_name: "E2E Admin" },
    action: "user.invited",
    target_type: "user",
    target_id: "11111111-1111-4111-8111-111111111111",
    metadata: { email: "ada@example.test", role: "marketer" },
    ...overrides,
  };
}

/** Page de GET /api/v1/admin/audit-log : `{ items, next_cursor }`. */
export function auditPage(items: unknown[], nextCursor: string | null = null) {
  return { items, next_cursor: nextCursor };
}

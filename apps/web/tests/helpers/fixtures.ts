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

const TARGET_METRICS = { mae: 0.0733, rmse: 0.0852, r2: -0.0342, baseline_mae: 0.0725 };

/** Mesures d'une version (DATA_MODEL.md 4.7) : fiabilité faible, comme avec le jeu de départ. */
export function metricsFixture(reliability = "low") {
  const figure = { ...TARGET_METRICS, reliability };
  return {
    click_through_rate: figure,
    conversion_rate: figure,
    website_visits: { ...figure, mae: 12.4, rmse: 14.5, baseline_mae: 12.3 },
    overall_reliability: reliability,
  };
}

/** Importance globale : trois chiffres, parts décroissantes. */
export function importanceFixture() {
  const shares = [
    { field: "ad_spend", share: 0.6 },
    { field: "campaign_channel", share: 0.4 },
  ];
  return { click_through_rate: shares, conversion_rate: shares, website_visits: shares };
}

/** Version du modèle (liste et détail de GET /api/v1/admin/model-versions). */
export function modelVersionFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    version: 3,
    status: "succeeded",
    data_scope: "all",
    is_active: false,
    created_at: "2026-10-04T10:00:00+00:00",
    finished_at: "2026-10-04T10:01:00+00:00",
    requested_by: { id: ADMIN_ID, full_name: "E2E Admin" },
    metrics: metricsFixture(),
    global_importance: importanceFixture(),
    features_used: ["ad_spend", "campaign_channel"],
    train_row_count: 6398,
    holdout_row_count: 1602,
    error_message: null,
    started_at: "2026-10-04T10:00:05+00:00",
    activated_at: null,
    ...overrides,
  };
}

/** Modèle actif (GET /api/v1/model/active). */
export function activeModelFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    version: 3,
    data_scope: "all",
    trained_at: "2026-10-04T10:01:00Z",
    activated_at: "2026-10-04T10:02:00Z",
    train_row_count: 6398,
    holdout_row_count: 1602,
    reliability: "low",
    metrics: metricsFixture(),
    global_importance: importanceFixture(),
    ...overrides,
  };
}

/** Résultat de POST /api/v1/predictions/simulate (API_SPEC.md 5.2), valeurs factices. */
export function predictionFixture(overrides: Partial<Record<string, unknown>> = {}) {
  const drivers = [
    { field: "ad_spend", value: 5000, contribution: 0.004, direction: "up" },
    { field: "campaign_channel", value: "Email", contribution: -0.002, direction: "down" },
  ];
  return {
    id: null,
    created_at: null,
    label: null,
    model_version: { id: "22222222-2222-4222-8222-222222222222", version: 3 },
    input: {},
    predictions: { click_through_rate: 0.121, conversion_rate: 0.0408, website_visits: 36.11 },
    derived: { estimated_leads: 1.47, estimated_cost_per_result: 3397.87 },
    performance: {
      score: 31.3,
      level: "low",
      notes: { click_through_rate: 42.7, estimated_leads: 30.8, estimated_cost_per_result: 20.4 },
      thresholds: { low_below: 40.4, high_from: 59.6 },
      reference: "campaign_type",
    },
    drivers: { click_through_rate: drivers, conversion_rate: drivers, website_visits: drivers },
    recommendations: {
      status: "found",
      items: [
        {
          lever: "campaign_channel",
          from_value: "Email",
          to_value: "PPC",
          score_gain: 36.3,
          new_score: 67.6,
          new_level: "high",
          new_predictions: { click_through_rate: 0.12, conversion_rate: 0.1, website_visits: 36 },
          new_derived: { estimated_leads: 3.9, estimated_cost_per_result: 1268.61 },
        },
      ],
    },
    warnings: [
      {
        code: "OUT_OF_TRAINING_RANGE",
        field: "ad_spend",
        message: "Outside the values the model has seen. Treat this prediction with caution.",
      },
    ],
    ...overrides,
  };
}

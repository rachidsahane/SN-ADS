import { expect, test } from "@playwright/test";

// Phase 2 : la page d'accueil provisoire (statuts API et base) est supprimée, ses quatre tests
// d'interface disparaissent avec elle. Restent les deux tests qui prouvent que l'API et sa
// disponibilité sont joignables par l'origine du site (rewrite /api/*).

test("API health is reachable through the web origin", async ({ request }) => {
  const response = await request.get("/api/health");

  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ok");
  expect(body.release).toBeTruthy();
});

test("API readiness is reachable through the web origin", async ({ request }) => {
  const response = await request.get("/api/ready");

  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ready");
  expect(body.checks.database).toBe("ok");
  expect(body.checks.cache).toBe("ok");
  expect(body.schema_version).toMatch(/^\d{14}$/);
  expect(body.release).toBeTruthy();
  const headers = response.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
});

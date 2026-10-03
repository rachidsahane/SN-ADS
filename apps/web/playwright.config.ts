import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // http://web:3000 n'est pas un contexte sécurisé (pas de crypto.subtle, requis par la
        // connexion Supabase en phase 2) : Chromium le traite comme sécurisé pour les tests.
        launchOptions: {
          args: [`--unsafely-treat-insecure-origin-as-secure=${new URL(baseURL).origin}`],
        },
      },
    },
    // Firefox et WebKit exécutent seulement les scénarios marqués @cross (TESTING.md section 3).
    { name: "firefox", use: { ...devices["Desktop Firefox"] }, grep: /@cross/ },
    { name: "webkit", use: { ...devices["Desktop Safari"] }, grep: /@cross/ },
  ],
});

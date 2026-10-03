import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
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
        // Le drapeau ci-dessous n'est honoré que par le Chromium complet (nouveau mode headless) : le
        // « headless shell » par défaut l'ignore (isSecureContext reste faux, vérifié en phase 2).
        channel: "chromium",
        // http://web:3000 n'est pas un contexte sécurisé (pas de crypto.subtle, requis par la
        // connexion Supabase en phase 2) : Chromium le traite comme sécurisé pour les tests.
        launchOptions: {
          args: [`--unsafely-treat-insecure-origin-as-secure=${new URL(baseURL).origin}`],
        },
      },
    },
    // Firefox et WebKit exécutent seulement les scénarios marqués @cross (TESTING.md section 3).
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        // http://web:3000 (réseau Compose) n'est pas HTTPS : Firefox y émet un avertissement de console sur les
        // champs mot de passe, que les scénarios interdisent. On le déclare contexte sécurisé, comme pour
        // Chromium ci-dessus ; la mise à niveau des contenus mixtes (inutile ici) est coupée.
        launchOptions: {
          firefoxUserPrefs: {
            "dom.securecontext.allowlist": new URL(baseURL).hostname,
            "security.mixed_content.upgrade_display_content": false,
            "security.mixed_content.block_display_content": false,
          },
        },
      },
      grep: /@cross/,
    },
    { name: "webkit", use: { ...devices["Desktop Safari"] }, grep: /@cross/ },
  ],
});

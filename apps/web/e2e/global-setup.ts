import { chromium } from "@playwright/test";

import { getAccounts } from "./fixtures/data";

/**
 * Préchauffe le serveur de développement Next.js (pitfall P11) : la première visite d'une page la compile et
 * peut dépasser le délai des assertions. On connecte un compte jetable une fois et on ouvre chaque page de
 * la phase pour que les scénarios mesurent le comportement, pas la compilation. Aucune assertion ici.
 */
export default async function globalSetup(): Promise<void> {
  const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const { marketerA } = getAccounts();

  const browser = await chromium.launch({
    args: [`--unsafely-treat-insecure-origin-as-secure=${new URL(baseURL).origin}`],
  });
  try {
    const context = await browser.newContext({ baseURL });
    const page = await context.newPage();
    page.setDefaultTimeout(120_000);

    await page.goto("/forgot-password");
    await page.goto("/auth/confirm");
    await page.goto("/login");
    await page.getByLabel("Email").fill(marketerA.email);
    await page.getByLabel("Password").fill(marketerA.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL(/\/predict$/);
    await page.getByTestId("user-name").waitFor();
    await page.goto("/auth/set-password");
    await page.getByRole("button", { name: "Set password" }).waitFor();
    await context.close();
  } finally {
    await browser.close();
  }
}

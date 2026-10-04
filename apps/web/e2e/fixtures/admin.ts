import { randomBytes } from "node:crypto";

import { expect, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { confirmPathFromMail, signIn, waitForHydratedForm, waitForMail } from "./auth";
import { type Account, getAccounts } from "./data";

// Outils des scénarios de la phase 3 (gestion des utilisateurs et audit). Aucun secret : les mots de
// passe sont générés à l'exécution, les adresses sont uniques à chaque appel, et le jeton d'accès
// est lu dans l'en-tête que l'application envoie déjà à l'API (aucune variable Supabase dans `e2e`).

export type InviteInput = { email: string; fullName: string; role: "Marketer" | "Admin" };

export type ProvisionedUser = {
  email: string;
  fullName: string;
  password: string;
  context: BrowserContext;
  page: Page;
};

/** Adresse jetable unique : `e2e-<prefix>-<12 hex>@example.test`. */
export function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${randomBytes(6).toString("hex")}@example.test`;
}

/** Mot de passe jetable généré à l'exécution (10 caractères minimum exigés par l'écran). */
export function runtimePassword(prefix = "Passw0rd"): string {
  return `${prefix}-${randomBytes(9).toString("hex")}`;
}

/** Connexion complète d'un administrateur ; attend l'arrivée sur /predict. */
export async function signInAsAdmin(page: Page, account: Account): Promise<void> {
  await signIn(page, account);
}

/**
 * Renvoie le jeton d'accès de la session : on écoute les requêtes AVANT toute navigation et on garde
 * l'en-tête `Authorization` de la première requête vers `/api/v1/me` (l'en-tête de l'application la
 * fait à chaque page). Avec `account`, la connexion est faite ici ; sans, la page est rechargée sur
 * /predict (session déjà ouverte).
 */
export async function captureAccessToken(page: Page, account?: Account): Promise<string> {
  const captured = new Promise<string>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("No Authorization header seen on /api/v1/me")),
      20_000,
    );
    page.on("request", (request) => {
      if (!new URL(request.url()).pathname.endsWith("/api/v1/me")) return;
      const header = request.headers()["authorization"];
      if (header?.startsWith("Bearer ")) {
        clearTimeout(timer);
        resolve(header.slice("Bearer ".length));
      }
    });
  });
  // Évite un rejet non géré si la connexion échoue avant la capture.
  captured.catch(() => undefined);
  if (account) {
    await signIn(page, account);
  } else {
    await page.goto("/predict");
  }
  return captured;
}

/**
 * Ouvre la page Users, sans la recharger si on y est déjà : chaque rechargement complet coûte plusieurs
 * secondes au serveur de développement sous charge, et la liste affichée est déjà rafraîchie depuis
 * l'API après chaque invitation ou modification (invalidation des requêtes).
 */
async function showUsers(page: Page): Promise<void> {
  if (new URL(page.url(), "http://placeholder.invalid").pathname !== "/admin/users") {
    await page.goto("/admin/users");
  }
}

/** Ouvre la page Users et la fenêtre « Invite user ». */
export async function openInviteDialog(page: Page): Promise<void> {
  await showUsers(page);
  await expect(page.getByRole("heading", { level: 1, name: "Users" })).toBeVisible();
  await page.getByRole("button", { name: "Invite user" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
}

/** Remplit la fenêtre d'invitation et l'envoie, sans attendre le résultat. */
export async function submitInvite(page: Page, input: InviteInput): Promise<void> {
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Email").fill(input.email);
  await dialog.getByLabel("Full name").fill(input.fullName);
  await dialog.getByLabel("Role", { exact: true }).selectOption({ label: input.role });
  await dialog.getByRole("button", { name: "Send invitation" }).click();
}

/** Invitation complète par l'interface ; attend le message de confirmation. */
export async function inviteViaUi(page: Page, input: InviteInput): Promise<void> {
  await openInviteDialog(page);
  await submitInvite(page, input);
  await expect(page.getByText(`Invitation sent to ${input.email}.`)).toBeVisible();
}

/** La ligne du tableau Users portant cette adresse. */
export function userRow(page: Page, email: string) {
  return page.getByTestId("user-row").filter({ hasText: email });
}

/** Les lignes du journal d'audit pour cette adresse et cette action. */
/** Lignes du journal pour une cible (nom complet : la cible s'affiche par nom, plus par e-mail) et une action. */
export function auditRows(page: Page, target: string, action: string) {
  return page
    .getByTestId("audit-row")
    .filter({ hasText: target })
    .filter({ has: page.getByTestId("audit-action").filter({ hasText: action }) });
}

/** Ouvre le lien d'invitation dans un contexte neuf et pose un mot de passe ; renvoie la page sur /predict. */
export async function acceptInvitation(
  adminPage: Page,
  browser: Browser,
  email: string,
  password: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const { mailpitUrl } = getAccounts();
  const mail = await waitForMail(adminPage.request, mailpitUrl, email, {
    subjectIncludes: "invited",
  });
  const path = confirmPathFromMail(mail);
  const context = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
  });
  const page = await context.newPage();
  await page.goto(path);
  await expect(page).toHaveURL(/\/auth\/set-password$/);
  await waitForHydratedForm(page);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page).toHaveURL(/\/predict$/);
  return { context, page };
}

/**
 * Crée un utilisateur actif : invitation par l'interface (page `adminPage` déjà connectée en
 * administrateur), lecture de l'e-mail dans Mailpit, ouverture du lien dans un contexte neuf, mot de
 * passe généré à l'exécution. L'appelant ferme `context`.
 */
export async function provisionActiveUser(
  adminPage: Page,
  browser: Browser,
  options: { role: "Marketer" | "Admin"; namePrefix?: string },
): Promise<ProvisionedUser> {
  const email = uniqueEmail(options.namePrefix ?? "user");
  const fullName = `E2E Provisioned ${randomBytes(3).toString("hex")}`;
  const password = runtimePassword();
  await inviteViaUi(adminPage, { email, fullName, role: options.role });
  const { context, page } = await acceptInvitation(adminPage, browser, email, password);
  return { email, fullName, password, context, page };
}

export const ACCOUNT_DISABLED_MESSAGE =
  "Your account has been deactivated. Contact an administrator.";

/** Désactive l'utilisateur depuis la page Users et attend le statut « Deactivated ». */
export async function deactivateViaUi(adminPage: Page, email: string): Promise<void> {
  await showUsers(adminPage);
  const row = userRow(adminPage, email);
  await row.getByRole("button", { name: "Deactivate" }).click();
  await expect(row.getByTestId("user-status")).toHaveText("Deactivated");
  await expect(row.getByRole("button", { name: "Reactivate" })).toBeVisible();
}

/** Réactive l'utilisateur depuis la page Users et attend le statut « Active ». */
export async function reactivateViaUi(adminPage: Page, email: string): Promise<void> {
  await showUsers(adminPage);
  const row = userRow(adminPage, email);
  await row.getByRole("button", { name: "Reactivate" }).click();
  await expect(row.getByTestId("user-status")).toHaveText("Active");
}

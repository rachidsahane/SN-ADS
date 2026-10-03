import { expect, type APIRequestContext, type Page } from "@playwright/test";

import type { Account } from "./data";

// Accès à Supabase Auth depuis Playwright (décision de la phase 2, voir D-069) :
// le conteneur `e2e` ne parle QU'à `http://web:3000`. Le navigateur appelle `/auth/v1/*` sur sa
// propre origine ; Next.js relaie vers Kong (AUTH_PROXY_TARGET). Aucune URL Kong n'est utilisée
// ici, et aucun CORS n'est en jeu. Le lien des e-mails porte l'origine SITE_URL
// (http://localhost:3000), inatteignable depuis ce conteneur : on ne garde que chemin + requête.

export const SIGN_IN_ERROR = "Invalid email or password.";
export const INVALID_LINK_MESSAGE =
  "This link is invalid or has expired. Ask an administrator for a new invitation.";

/** Collecte les erreurs et avertissements de console et les exceptions de la page. */
export function collectBrowserProblems(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      problems.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  return problems;
}

/**
 * Attend que React ait hydraté le formulaire de la page : en développement, sur une machine chargée,
 * l'hydratation peut arriver bien après le chargement, et un clic donné avant elle est perdu. React
 * pose `__reactProps$…` sur un élément hydraté, ce qui ne dépend ni du réseau ni d'un délai fixe.
 */
export async function waitForHydratedForm(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const form = document.querySelector("form");
    return form !== null && Object.keys(form).some((key) => key.startsWith("__reactProps$"));
  });
}

/** Remplit le formulaire "Sign in" sans le soumettre. */
export async function fillSignIn(page: Page, account: Account): Promise<void> {
  await page.goto("/login");
  await waitForHydratedForm(page);
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Password").fill(account.password);
}

/** Connexion complète par l'interface ; attend l'arrivée sur /predict. */
export async function signIn(page: Page, account: Account): Promise<void> {
  await fillSignIn(page, account);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/predict$/);
}

/** Le bandeau d'erreur du formulaire (le Next.js route announcer porte aussi role="alert"). */
export function alertWithText(page: Page, text: string) {
  return page.getByRole("alert").filter({ hasText: text });
}

export type MailMessage = { id: string; subject: string; html: string; text: string };

/** Supprime les messages déjà reçus par cette adresse (comptes dédiés à un seul test). */
export async function clearMailbox(
  request: APIRequestContext,
  mailpitUrl: string,
  toAddress: string,
): Promise<void> {
  const response = await request.delete(
    `${mailpitUrl}/api/v1/search?query=${encodeURIComponent(`to:${toAddress}`)}`,
  );
  expect(response.ok()).toBeTruthy();
}

/** Attend (15 s au plus) le message le plus récent adressé à `toAddress` dont le sujet convient. */
export async function waitForMail(
  request: APIRequestContext,
  mailpitUrl: string,
  toAddress: string,
  options: { subjectIncludes: string },
): Promise<MailMessage> {
  let found: MailMessage | undefined;
  await expect
    .poll(
      async () => {
        const search = await request.get(
          `${mailpitUrl}/api/v1/search?query=${encodeURIComponent(`to:${toAddress}`)}`,
        );
        if (!search.ok()) return false;
        const listing = (await search.json()) as {
          messages?: { ID: string; Subject: string }[];
        };
        // Mailpit renvoie les messages du plus récent au plus ancien.
        const hit = (listing.messages ?? []).find((message) =>
          message.Subject.includes(options.subjectIncludes),
        );
        if (!hit) return false;
        const detail = await request.get(`${mailpitUrl}/api/v1/message/${hit.ID}`);
        if (!detail.ok()) return false;
        const body = (await detail.json()) as { HTML: string; Text: string; Subject: string };
        found = { id: hit.ID, subject: body.Subject, html: body.HTML, text: body.Text };
        return true;
      },
      { timeout: 15_000, message: `no mail "${options.subjectIncludes}" for ${toAddress}` },
    )
    .toBe(true);
  if (!found) throw new Error("unreachable: mail not found");
  return found;
}

/**
 * Extrait le lien /auth/confirm du message et renvoie UNIQUEMENT chemin + requête
 * (l'origine du lien est SITE_URL, pas l'adresse que Playwright atteint).
 */
export function confirmPathFromMail(message: MailMessage): string {
  const match = /href="([^"]*\/auth\/confirm[^"]*)"/.exec(message.html);
  if (!match?.[1]) {
    throw new Error("No /auth/confirm link in the e-mail");
  }
  const href = match[1].replaceAll("&amp;", "&");
  const url = new URL(href);
  return `${url.pathname}${url.search}`;
}

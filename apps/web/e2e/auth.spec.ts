import { randomBytes } from "node:crypto";

import { expect, test } from "@playwright/test";

import {
  INVALID_LINK_MESSAGE,
  SIGN_IN_ERROR,
  alertWithText,
  clearMailbox,
  collectBrowserProblems,
  confirmPathFromMail,
  fillSignIn,
  signIn,
  waitForHydratedForm,
  waitForMail,
} from "./fixtures/auth";
import {
  ACCOUNT_DISABLED_MESSAGE,
  deactivateViaUi,
  inviteViaUi,
  provisionActiveUser,
  reactivateViaUi,
  runtimePassword,
  signInAsAdmin,
  uniqueEmail,
  userRow,
} from "./fixtures/admin";
import { getAccounts } from "./fixtures/data";

// Comptes créés avant Playwright par `make test-users` (conteneur `cli`, voir fixtures/data.ts).
// Valeurs jetables générées à l'exécution : jamais de mot de passe écrit dans un fichier.
const runtimeSecret = (prefix: string): string => `${prefix}-${randomBytes(9).toString("hex")}`;

test.describe("authentication", () => {
  test("E2E-AUTH-01 sign in lands on Predict with the user name in the header @cross @smoke", async ({
    page,
  }) => {
    const { marketerA } = getAccounts();
    const problems = collectBrowserProblems(page);

    await signIn(page, marketerA);

    await expect(page).toHaveURL(/\/predict$/);
    await expect(page.getByRole("heading", { level: 1, name: "Predict" })).toBeVisible();
    await expect(page.getByTestId("user-name")).toHaveText("E2E Marketer A");
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("E2E-AUTH-02 a wrong password shows the generic error and stays on Sign in", async ({
    page,
  }) => {
    const { marketerB } = getAccounts();

    await fillSignIn(page, { email: marketerB.email, password: runtimeSecret("wrong") });
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(alertWithText(page, SIGN_IN_ERROR)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  });

  test("E2E-AUTH-03 an unknown e-mail shows exactly the same error as a wrong password", async ({
    page,
  }) => {
    await fillSignIn(page, {
      email: `unknown-${randomBytes(6).toString("hex")}@example.test`,
      password: runtimeSecret("unknown"),
    });
    await page.getByRole("button", { name: "Sign in" }).click();

    const alert = alertWithText(page, SIGN_IN_ERROR);
    await expect(alert).toBeVisible();
    await expect(alert).toHaveText(SIGN_IN_ERROR);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  });

  test("E2E-AUTH-04 after Sign out a direct visit to /predict goes back to Sign in", async ({
    page,
  }) => {
    const { marketerA } = getAccounts();
    await signIn(page, marketerA);

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.goto("/predict");

    await expect(page).toHaveURL(/\/login\?next=%2Fpredict$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
    await expect(page.getByTestId("user-name")).toHaveCount(0);
    await expect(page.getByText("E2E Marketer A")).toHaveCount(0);
  });

  test("E2E-AUTH-06 an invitation link works once, a second use shows the invalid-link message", async ({
    page,
    request,
    browser,
    baseURL,
  }) => {
    const { inviteeEmail, mailpitUrl } = getAccounts();
    // L'invitation a été envoyée par `make test-users` ; on prend le message le plus récent.
    const mail = await waitForMail(request, mailpitUrl, inviteeEmail, {
      subjectIncludes: "invited",
    });
    const path = confirmPathFromMail(mail);
    expect(path).toMatch(
      /^\/auth\/confirm\?token_hash=[^&]+&type=invite&next=\/auth\/set-password$/,
    );

    // Première ouverture : l'invité arrive sur "Set your password".
    const problems = collectBrowserProblems(page);
    await page.goto(path);
    await expect(page).toHaveURL(/\/auth\/set-password$/);
    await expect(page.getByRole("heading", { level: 1, name: "Set your password" })).toBeVisible();
    expect(problems).toEqual([]);

    // Seconde ouverture, dans un contexte neuf (aucune session) : lien déjà consommé.
    const fresh = await browser.newContext({ baseURL });
    try {
      const second = await fresh.newPage();
      await second.goto(path);
      await expect(second).toHaveURL(/\/login\?reason=invalid_link$/);
      await expect(alertWithText(second, INVALID_LINK_MESSAGE)).toBeVisible();
      await expect(second.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
    } finally {
      await fresh.close();
    }
  });

  test("E2E-AUTH-07 forgot password: e-mail received, new password set, sign in with it", async ({
    page,
    request,
  }) => {
    const { reset, mailpitUrl } = getAccounts();
    // Compte dédié à ce seul test (les autres suites tournent en parallèle sur A et B) ;
    // une seule demande par exécution : gotrue limite à une par minute et par utilisateur.
    await clearMailbox(request, mailpitUrl, reset.email);

    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot password?" }).click();
    await expect(page).toHaveURL(/\/forgot-password$/);
    await waitForHydratedForm(page);
    await page.getByLabel("Email").fill(reset.email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(
      page.getByText(
        "If an account exists for this email, a reset link has been sent. It opens the “Set your password” screen.",
      ),
    ).toBeVisible();

    const mail = await waitForMail(request, mailpitUrl, reset.email, {
      subjectIncludes: "Reset your",
    });
    const path = confirmPathFromMail(mail);
    expect(path).toMatch(
      /^\/auth\/confirm\?token_hash=[^&]+&type=recovery&next=\/auth\/set-password$/,
    );

    await page.goto(path);
    await expect(page).toHaveURL(/\/auth\/set-password$/);
    await expect(page.getByRole("heading", { level: 1, name: "Set your password" })).toBeVisible();
    await waitForHydratedForm(page);

    // Mot de passe trop court (9 caractères) : refusé.
    await page.getByLabel("Password", { exact: true }).fill("Abcdef123");
    await page.getByLabel("Confirm password").fill("Abcdef123");
    await page.getByRole("button", { name: "Set password" }).click();
    await expect(page.getByText("Password must be at least 10 characters.")).toBeVisible();
    await expect(page).toHaveURL(/\/auth\/set-password$/);

    // Mot de passe valide, différent de l'ancien : accepté, arrivée sur Predict.
    const newPassword = runtimeSecret("Newpass1");
    expect(newPassword).not.toBe(reset.password);
    await page.getByLabel("Password", { exact: true }).fill(newPassword);
    await page.getByLabel("Confirm password").fill(newPassword);
    await page.getByRole("button", { name: "Set password" }).click();
    await expect(page).toHaveURL(/\/predict$/);

    // Déconnexion puis connexion avec le nouveau mot de passe.
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await signIn(page, { email: reset.email, password: newPassword });
    await expect(page.getByRole("heading", { level: 1, name: "Predict" })).toBeVisible();
  });
  test("E2E-AUTH-05 an invited user sets a password, lands on Predict and becomes Active", async ({
    page,
    request,
    browser,
    baseURL,
  }) => {
    const { admin, mailpitUrl } = getAccounts();
    const email = uniqueEmail("auth05");
    const fullName = "E2E Invited Five";
    await signInAsAdmin(page, admin);
    await inviteViaUi(page, { email, fullName, role: "Marketer" });
    await expect(userRow(page, email).getByTestId("user-status")).toHaveText("Invited");

    const mail = await waitForMail(request, mailpitUrl, email, { subjectIncludes: "invited" });
    const path = confirmPathFromMail(mail);
    expect(path).toMatch(
      /^\/auth\/confirm\?token_hash=[^&]+&type=invite&next=\/auth\/set-password$/,
    );

    const fresh = await browser.newContext({ baseURL });
    try {
      const invitee = await fresh.newPage();
      const problems = collectBrowserProblems(invitee);
      await invitee.goto(path);
      await expect(invitee).toHaveURL(/\/auth\/set-password$/);
      await expect(
        invitee.getByRole("heading", { level: 1, name: "Set your password" }),
      ).toBeVisible();
      await waitForHydratedForm(invitee);

      // Mot de passe trop court (9 caractères) : refusé.
      await invitee.getByLabel("Password", { exact: true }).fill("Abcdef123");
      await invitee.getByLabel("Confirm password").fill("Abcdef123");
      await invitee.getByRole("button", { name: "Set password" }).click();
      await expect(invitee.getByText("Password must be at least 10 characters.")).toBeVisible();
      await expect(invitee).toHaveURL(/\/auth\/set-password$/);

      const password = runtimePassword();
      await invitee.getByLabel("Password", { exact: true }).fill(password);
      await invitee.getByLabel("Confirm password").fill(password);
      await invitee.getByRole("button", { name: "Set password" }).click();
      await expect(invitee).toHaveURL(/\/predict$/);
      await expect(invitee.getByTestId("user-name")).toHaveText(fullName);
      expect(problems).toEqual([]);
    } finally {
      await fresh.close();
    }

    // De retour chez l'administrateur : "Invited" est devenu "Active".
    await page.goto("/admin/users");
    await expect(userRow(page, email).getByTestId("user-status")).toHaveText("Active");
  });

  test("E2E-AUTH-08 a deactivated user is refused with the deactivation message until reactivated", async ({
    page,
    browser,
    baseURL,
  }) => {
    const { admin } = getAccounts();
    await signInAsAdmin(page, admin);
    const user = await provisionActiveUser(page, browser, {
      role: "Marketer",
      namePrefix: "auth08",
    });
    await user.context.close();

    await deactivateViaUi(page, user.email);

    const fresh = await browser.newContext({ baseURL });
    try {
      const attempt = await fresh.newPage();
      await fillSignIn(attempt, { email: user.email, password: user.password });
      await attempt.getByRole("button", { name: "Sign in" }).click();
      await expect(alertWithText(attempt, ACCOUNT_DISABLED_MESSAGE)).toBeVisible();
      await expect(attempt).toHaveURL(/\/login$/);

      await reactivateViaUi(page, user.email);

      await signIn(attempt, { email: user.email, password: user.password });
      await expect(attempt.getByRole("heading", { level: 1, name: "Predict" })).toBeVisible();
    } finally {
      await fresh.close();
    }
  });
});

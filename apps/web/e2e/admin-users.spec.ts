import { expect, test } from "@playwright/test";

import {
  auditRows,
  captureAccessToken,
  inviteViaUi,
  openInviteDialog,
  signInAsAdmin,
  submitInvite,
  uniqueEmail,
  userRow,
} from "./fixtures/admin";
import { collectBrowserProblems } from "./fixtures/auth";
import { getAccounts } from "./fixtures/data";

// Phase 3 : gestion des utilisateurs par un administrateur (E2E-USR-01 à 05).
// Règles communes : adresses uniques à chaque appel (jamais E2E_INVITEE_EMAIL, réservée à
// E2E-AUTH-06) ; on ne modifie que des utilisateurs créés par le scénario lui-même, jamais un
// compte de test partagé (les scénarios tournent en parallèle).

const ALREADY_EXISTS = "A user with this email already exists.";
const LAST_ADMIN_MESSAGE = "At least one active administrator is required.";

test.describe("admin: users", () => {
  test("E2E-USR-01 inviting a marketer shows it as Invited and writes a user.invited audit entry", async ({
    page,
  }) => {
    const { admin } = getAccounts();
    const email = uniqueEmail("usr01");
    const fullName = `E2E Invited ${email.split("@")[0]}`; // unique: the audit log shows the name
    await signInAsAdmin(page, admin);
    const problems = collectBrowserProblems(page);

    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { level: 1, name: "Users" })).toBeVisible();
    await page.getByRole("button", { name: "Invite user" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await submitInvite(page, { email, fullName, role: "Marketer" });

    await expect(page.getByText(`Invitation sent to ${email}.`)).toBeVisible();
    await expect(dialog).toBeHidden();
    const row = userRow(page, email);
    await expect(row).toHaveCount(1);
    await expect(row.getByTestId("user-status")).toHaveText("Invited");

    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { level: 1, name: "Audit log" })).toBeVisible();
    const entry = auditRows(page, fullName, "user.invited");
    await expect(entry).toHaveCount(1);
    await expect(entry.getByTestId("audit-action")).toHaveText("user.invited");
    await expect(entry).toContainText("Role: marketer");
    await expect(entry).toContainText("E2E Admin");

    expect(problems).toEqual([]);
  });

  test("E2E-USR-02 inviting an existing address is refused and creates no row", async ({
    page,
  }) => {
    const { admin, marketerA } = getAccounts();
    await signInAsAdmin(page, admin);

    // Cas 1 : un utilisateur déjà actif (marketerA).
    await openInviteDialog(page);
    await expect(userRow(page, marketerA.email)).toHaveCount(1);
    await submitInvite(page, {
      email: marketerA.email,
      fullName: "E2E Duplicate",
      role: "Marketer",
    });
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText(ALREADY_EXISTS)).toBeVisible();
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(userRow(page, marketerA.email)).toHaveCount(1);

    // Cas 2 : une adresse déjà invitée par un premier appel.
    const invited = uniqueEmail("usr02");
    await inviteViaUi(page, { email: invited, fullName: "E2E Invited Two", role: "Marketer" });
    await expect(userRow(page, invited)).toHaveCount(1);

    await openInviteDialog(page);
    await submitInvite(page, { email: invited, fullName: "E2E Invited Twice", role: "Marketer" });
    await expect(page.getByRole("dialog").getByText(ALREADY_EXISTS)).toBeVisible();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
    await expect(userRow(page, invited)).toHaveCount(1);
  });

  test("E2E-USR-03 a role change to Admin and back is visible in the list and in the audit log", async ({
    page,
  }) => {
    const { admin } = getAccounts();
    const email = uniqueEmail("usr03");
    const fullName = `E2E Role ${email.split("@")[0]}`; // unique: the audit log shows the name
    await signInAsAdmin(page, admin);
    const problems = collectBrowserProblems(page);

    await inviteViaUi(page, { email, fullName, role: "Marketer" });
    const select = userRow(page, email).getByRole("combobox", { name: `Role for ${email}` });
    await expect(select.locator("option:checked")).toHaveText("Marketer");

    const toAdmin = page.waitForResponse(
      (response) => response.request().method() === "PATCH" && response.status() === 200,
    );
    await select.selectOption({ label: "Admin" });
    await toAdmin;
    await page.reload();
    await expect(
      userRow(page, email)
        .getByRole("combobox", { name: `Role for ${email}` })
        .locator("option:checked"),
    ).toHaveText("Admin");

    const toMarketer = page.waitForResponse(
      (response) => response.request().method() === "PATCH" && response.status() === 200,
    );
    await userRow(page, email)
      .getByRole("combobox", { name: `Role for ${email}` })
      .selectOption({ label: "Marketer" });
    await toMarketer;
    await page.reload();
    await expect(
      userRow(page, email)
        .getByRole("combobox", { name: `Role for ${email}` })
        .locator("option:checked"),
    ).toHaveText("Marketer");

    await page.goto("/admin/audit");
    const entries = auditRows(page, fullName, "user.role_changed");
    await expect(entries).toHaveCount(2);
    // Le plus récent d'abord : retour à Marketer, puis passage à Admin.
    await expect(entries.nth(0)).toContainText("admin → marketer");
    await expect(entries.nth(1)).toContainText("marketer → admin");

    expect(problems).toEqual([]);
  });

  test("E2E-USR-04 an administrator cannot act on their own account, in the UI or through the API", async ({
    page,
    request,
    browser,
  }) => {
    const { admin } = getAccounts();
    const token = await captureAccessToken(page, admin);
    const problems = collectBrowserProblems(page);

    await page.goto("/admin/users");
    const own = userRow(page, admin.email);
    await expect(own).toHaveCount(1);
    await expect(own).toContainText("(you)");
    await expect(own.getByRole("combobox", { name: `Role for ${admin.email}` })).toBeDisabled();
    await expect(own.getByRole("button", { name: "Deactivate" })).toBeDisabled();
    expect(problems).toEqual([]);

    const headers = { Authorization: `Bearer ${token}` };
    const me = await request.get("/api/v1/me", { headers });
    expect(me.status()).toBe(200);
    const ownId = ((await me.json()) as { id: string }).id;

    for (const body of [{ role: "marketer" }, { is_active: false }]) {
      const response = await request.patch(`/api/v1/admin/users/${ownId}`, {
        headers,
        data: body,
      });
      expect(response.status()).toBe(409);
      const payload = (await response.json()) as {
        error: { code: string; message: string; request_id: string };
      };
      expect(payload.error.code).toBe("SELF_ACTION_FORBIDDEN");
      expect(payload.error.message).toBeTruthy();
      expect(payload.error.request_id).toBeTruthy();
    }

    // L'état n'a pas changé : l'administrateur se reconnecte et reste administrateur actif.
    const other = await browser.newContext({
      baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    });
    try {
      const again = await other.newPage();
      await signInAsAdmin(again, admin);
      await again.goto("/admin/users");
      await expect(again.getByRole("heading", { level: 1, name: "Users" })).toBeVisible();
    } finally {
      await other.close();
    }
  });

  test("E2E-USR-05 the last-administrator refusal is shown as received and the role returns to its server value", async ({
    page,
  }) => {
    const { admin } = getAccounts();
    const email = uniqueEmail("usr05");
    await signInAsAdmin(page, admin);
    await inviteViaUi(page, { email, fullName: "E2E Last Admin", role: "Marketer" });

    // UI seule (D-089) : la base refuse réellement ce cas (pgTAP 030, test d'intégration), ici on
    // vérifie l'affichage d'un 409 LAST_ADMIN renvoyé par l'API.
    await page.route("**/api/v1/admin/users/*", async (route) => {
      if (route.request().method() !== "PATCH") {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "LAST_ADMIN",
            message: LAST_ADMIN_MESSAGE,
            details: [],
            request_id: "00000000-0000-4000-8000-0000000000e5",
          },
        }),
      });
    });

    const select = userRow(page, email).getByRole("combobox", { name: `Role for ${email}` });
    await select.selectOption({ label: "Admin" });

    await expect(page.getByRole("alert").filter({ hasText: LAST_ADMIN_MESSAGE })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: LAST_ADMIN_MESSAGE })).toHaveText(
      LAST_ADMIN_MESSAGE,
    );
    await expect(
      userRow(page, email)
        .getByRole("combobox", { name: `Role for ${email}` })
        .locator("option:checked"),
    ).toHaveText("Marketer");
  });
});

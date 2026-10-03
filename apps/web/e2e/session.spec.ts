import { expect, test } from "@playwright/test";

import {
  ACCOUNT_DISABLED_MESSAGE,
  deactivateViaUi,
  provisionActiveUser,
  signInAsAdmin,
} from "./fixtures/admin";
import { alertWithText } from "./fixtures/auth";
import { getAccounts } from "./fixtures/data";

// Phase 3 : un utilisateur désactivé pendant sa session est refusé à sa prochaine action (E2E-SESS-03).

test.describe("session", () => {
  test("E2E-SESS-03 a user deactivated during the session is sent back to Sign in with the deactivation message", async ({
    page,
    browser,
  }) => {
    const { admin } = getAccounts();
    await signInAsAdmin(page, admin);
    const user = await provisionActiveUser(page, browser, {
      role: "Marketer",
      namePrefix: "sess03",
    });
    try {
      const pageErrors: string[] = [];
      user.page.on("pageerror", (error) => pageErrors.push(error.message));
      await expect(user.page.getByTestId("user-name")).toHaveText(user.fullName);

      await deactivateViaUi(page, user.email);

      // Prochaine action de l'utilisateur : un rechargement.
      await user.page.reload();
      await expect(user.page).toHaveURL(/\/login/);
      await expect(alertWithText(user.page, ACCOUNT_DISABLED_MESSAGE)).toBeVisible();
      await expect(user.page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();

      // Il ne peut plus atteindre l'application.
      await user.page.goto("/predict");
      await expect(user.page).toHaveURL(/\/login/);
      await expect(user.page.getByTestId("user-name")).toHaveCount(0);
      expect(pageErrors).toEqual([]);
    } finally {
      await user.context.close();
    }
  });
});

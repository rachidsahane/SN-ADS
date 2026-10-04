import { expect, test } from "@playwright/test";

import { collectBrowserProblems, signIn } from "./fixtures/auth";
import { getAccounts } from "./fixtures/data";

// Démonstration : l'administrateur prédit, enregistre, retrouve la prédiction dans History et l'ouvre ;
// un autre utilisateur ne peut pas l'ouvrir (« Prediction not found. »). Un modèle doit être actif (make demo).

test.describe("demo path", () => {
  test("an administrator saves a prediction and finds it in History; another user cannot open it", async ({
    page,
    browser,
    baseURL,
  }) => {
    const { admin, marketerB } = getAccounts();
    await signIn(page, admin);
    const problems = collectBrowserProblems(page);

    await page.getByLabel("Ad spend (USD)").fill("5000");
    await expect(page.getByTestId("figure-card")).toHaveCount(3);
    const level = (await page.getByTestId("level-badge").textContent()) ?? "";

    const name = `Demo ${Date.now()}`;
    await page.getByRole("button", { name: "Save prediction" }).click();
    const dialog = page.getByRole("dialog", { name: "Save prediction" });
    await dialog.getByLabel("Name (optional)").fill(name);
    await dialog.getByRole("button", { name: "Save prediction" }).click();
    await expect(page.getByTestId("toast")).toHaveText("Prediction saved to History.");

    await page
      .getByRole("navigation", { name: "Main" })
      .getByRole("link", { name: "History" })
      .click();
    await expect(page).toHaveURL(/\/history$/);
    const row = page.getByTestId("history-row").filter({ hasText: name });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText(level);
    await row.getByRole("link", { name }).click();
    await expect(page).toHaveURL(/\/history\/[0-9a-f-]{36}$/);
    const detailUrl = page.url();
    // The saved prediction opens in the Predict screen, read-only until a field is edited.
    await expect(page.getByTestId("viewing-bar")).toContainText(name);
    await expect(page.getByTestId("figure-card")).toHaveCount(3);
    await expect(page.getByTestId("level-badge")).toHaveText(level);
    await expect(page.getByRole("button", { name: "Save prediction" })).toBeDisabled();

    // Another user (even with the exact URL) is told the prediction does not exist.
    const context = await browser.newContext({ baseURL });
    try {
      const other = await context.newPage();
      await signIn(other, marketerB);
      await other.goto(detailUrl);
      await expect(
        other.getByRole("alert").filter({ hasText: "Prediction not found." }),
      ).toHaveText("Prediction not found.");
    } finally {
      await context.close();
    }

    // The owner deletes it from History (inline confirmation): the row is gone.
    await page.getByTestId("viewing-bar").getByRole("link", { name: "Back to history" }).click();
    await expect(page).toHaveURL(/\/history$/);
    const mine = page.getByTestId("history-row").filter({ hasText: name });
    await mine.getByRole("button", { name: "Delete prediction" }).click();
    await mine.getByRole("button", { name: "Delete", exact: true }).click();
    await expect(page.getByTestId("toast")).toHaveText("Prediction deleted.");
    await expect(page.getByTestId("history-row").filter({ hasText: name })).toHaveCount(0);
    expect(problems).toEqual([]);
  });
});

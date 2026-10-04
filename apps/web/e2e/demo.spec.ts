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
    await page.getByRole("button", { name: "Predict" }).click();
    await expect(page.getByTestId("figure-card")).toHaveCount(5);
    const level = (await page.getByTestId("level-badge").textContent()) ?? "";

    const name = `Demo ${Date.now()}`;
    await page.getByRole("button", { name: "Save prediction" }).click();
    await page.getByLabel("Name").fill(name);
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByTestId("saved-notice")).toBeVisible();

    await page
      .getByRole("navigation", { name: "Main" })
      .getByRole("link", { name: "History" })
      .click();
    await expect(page).toHaveURL(/\/history$/);
    const row = page.getByTestId("history-row").filter({ hasText: name });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText(level);
    await row.getByRole("link", { name: "Open" }).click();
    await expect(page).toHaveURL(/\/history\/[0-9a-f-]{36}$/);
    const detailUrl = page.url();
    await expect(page.getByTestId("prediction-name")).toHaveText(name);
    await expect(page.getByTestId("figure-card")).toHaveCount(5);
    await expect(page.getByTestId("level-badge")).toHaveText(level);
    await expect(page.getByRole("button", { name: "Apply" })).toHaveCount(0);

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

    // The owner deletes it: back to History, the row is gone.
    await page.getByRole("button", { name: "Delete" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
    await expect(page).toHaveURL(/\/history$/);
    await expect(page.getByTestId("history-row").filter({ hasText: name })).toHaveCount(0);
    expect(problems).toEqual([]);
  });
});

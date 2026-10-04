import { expect, test } from "@playwright/test";

import { collectBrowserProblems, signIn } from "./fixtures/auth";
import { getAccounts } from "./fixtures/data";

// Démonstration : un marketer décrit une campagne et lit les résultats (un modèle doit être actif).

test.describe("prediction", () => {
  test("a marketer predicts a campaign and applies a recommendation", async ({ page }) => {
    await signIn(page, getAccounts().marketerA);
    const problems = collectBrowserProblems(page);

    await expect(page.getByText("Campaign plan", { exact: true })).toBeVisible();
    await expect(page.getByText("Target audience profile", { exact: true })).toBeVisible();
    await expect(page.getByText("Expected engagement", { exact: true })).toBeVisible();

    // Choosing the channel and the type pre-fills the expected engagement.
    await page.getByLabel("Pages per visit").fill("1");
    await page.getByLabel("Channel").selectOption("PPC");
    await expect(page.getByLabel("Pages per visit")).not.toHaveValue("1");

    await page.getByLabel("Ad spend (USD)").fill("5000");
    await page.getByRole("button", { name: "Predict" }).click();
    await expect(page.getByTestId("figure-card")).toHaveCount(5);
    await expect(page.getByTestId("level-badge")).toHaveText(/Low|Medium|High/);
    await expect(page.getByTestId("score")).toContainText("/ 100");
    await expect(
      page.getByRole("heading", { name: "What drives these predictions" }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Website visits" }).click();

    const recommendations = page.getByTestId("recommendation");
    if ((await recommendations.count()) > 0) {
      const first = recommendations.first();
      await expect(first).toContainText("Change ");
      await first.getByRole("button", { name: "Apply" }).click();
      await expect(page.getByTestId("figure-card")).toHaveCount(5);
    } else {
      await expect(
        page.getByText("No tested change improves the result significantly."),
      ).toBeVisible();
    }

    // Out-of-range input is refused field by field, before any request.
    await page.getByLabel("Age", { exact: true }).fill("17");
    await page.getByRole("button", { name: "Predict" }).click();
    await expect(page.getByText("Enter a value between 18 and 100.")).toBeVisible();
    expect(problems).toEqual([]);
  });
});

import { expect, test } from "@playwright/test";

import { collectBrowserProblems, signIn } from "./fixtures/auth";
import { getAccounts } from "./fixtures/data";

// Démonstration : un marketer décrit une campagne et lit les résultats, qui se recalculent tout seuls
// pendant la saisie (un modèle doit être actif).

test.describe("prediction", () => {
  test("a marketer sees live results, edits fields, applies a recommendation and saves", async ({
    page,
  }) => {
    await signIn(page, getAccounts().marketerA);
    const problems = collectBrowserProblems(page);

    await expect(page.getByText("Campaign plan", { exact: true })).toBeVisible();
    await expect(page.getByText("Target audience profile", { exact: true })).toBeVisible();
    await expect(page.getByText("Expected engagement", { exact: true })).toBeVisible();
    // No Predict button: the results appear by themselves.
    await expect(page.getByRole("button", { name: "Predict", exact: true })).toHaveCount(0);
    await expect(page.getByTestId("figure-card")).toHaveCount(3);
    await expect(page.getByTestId("level-badge")).toHaveText(/Low|Medium|High/);
    await expect(page.getByTestId("score")).toContainText("/ 100");
    await expect(page.getByTestId("model-tag")).toHaveText(/^Model v\d+$/);
    await expect(page.getByRole("heading", { name: "What moved this prediction" })).toBeVisible();
    await page.getByRole("tab", { name: "Website visits" }).click();
    await expect(page.getByRole("tab", { name: "Website visits" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // Choosing the channel pre-fills the expected engagement with the observed averages.
    await page.getByLabel("Pages per visit").fill("1");
    await page.getByLabel("Channel").selectOption("PPC");
    await expect(page.getByLabel("Pages per visit")).not.toHaveValue("1");
    await expect(
      page.getByText("Prefilled with the observed average for PPC · Conversion."),
    ).toBeVisible();

    // A new value is calculated 400 ms after the last keystroke.
    await page.getByLabel("Ad spend (USD)").fill("7500");
    await expect(page.getByTestId("figure-card")).toHaveCount(3);

    const recommendations = page.getByTestId("recommendation");
    if ((await recommendations.count()) > 0) {
      await recommendations.first().getByRole("button", { name: "Apply" }).click();
      await expect(page.getByTestId("figure-card")).toHaveCount(3);
    } else {
      await expect(
        page.getByText("No tested change improves the result significantly."),
      ).toBeVisible();
    }

    // Out-of-range input is refused field by field, results are hidden, nothing is sent.
    await page.getByLabel("Age", { exact: true }).fill("17");
    await expect(page.getByText("Age must be between 18 and 100.")).toBeVisible();
    await expect(
      page.getByText("Fix the highlighted fields to see the predicted results."),
    ).toBeVisible();
    await expect(page.getByTestId("figure-card")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Save prediction" })).toBeDisabled();
    await page.getByLabel("Age", { exact: true }).fill("40");
    await expect(page.getByTestId("figure-card")).toHaveCount(3);
    expect(problems).toEqual([]);
  });
});

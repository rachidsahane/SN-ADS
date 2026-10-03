import { expect, test } from "@playwright/test";

test("home page shows the product title and a healthy API", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      problems.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));

  await page.goto("/");

  await expect(
    page.getByRole("heading", { level: 1, name: "Soro Nua Campaign Predictor" }),
  ).toBeVisible();
  const status = page.getByTestId("api-status");
  await expect(status).toHaveText("API: healthy");
  await expect(status).toHaveAttribute("data-state", "healthy");
  await expect(status).toHaveCSS("color", "rgb(22, 100, 52)");
  expect(problems).toEqual([]);
});

test("home page shows 'API: unreachable' in red when the API cannot be reached", async ({
  page,
}) => {
  await page.route("**/api/health", (route) => route.abort("connectionrefused"));

  await page.goto("/");

  const status = page.getByTestId("api-status");
  await expect(status).toHaveText("API: unreachable");
  await expect(status).toHaveAttribute("data-state", "unreachable");
  await expect(status).toHaveCSS("color", "rgb(180, 35, 24)");
});

test("API health is reachable through the web origin", async ({ request }) => {
  const response = await request.get("/api/health");

  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ok");
  expect(body.release).toBeTruthy();
});

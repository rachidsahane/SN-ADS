import { expect, test } from "@playwright/test";

import { captureAccessToken, signInAsAdmin } from "./fixtures/admin";
import { collectBrowserProblems, signIn } from "./fixtures/auth";
import { ADMIN_API_ROUTES, ADMIN_PAGES, getAccounts } from "./fixtures/data";

// Phase 3 : un marketer n'atteint aucune page ni route d'administration (E2E-ISO-06 et 07).
// `ADMIN_PAGES` et `ADMIN_API_ROUTES` ne listent que ce qui existe ; les phases 5 et 8 les étendent.

test.describe("isolation: administration", () => {
  test("E2E-ISO-06 a marketer sees no admin links and is sent back to Predict from admin pages", async ({
    page,
    browser,
    baseURL,
  }) => {
    const { marketerB, admin } = getAccounts();
    const adminResponses: string[] = [];
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (url.pathname.startsWith("/api/v1/admin/") && response.ok()) {
        adminResponses.push(`${response.status()} ${url.pathname}`);
      }
    });
    await signIn(page, marketerB);
    const problems = collectBrowserProblems(page);

    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link", { name: "Predict" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Users" })).toHaveCount(0);
    await expect(nav.getByRole("link", { name: "Audit log" })).toHaveCount(0);

    for (const path of ADMIN_PAGES) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/predict\?notice=forbidden$/);
      // The prototype announces it with a short message (toast), not a persistent alert.
      await expect(page.getByTestId("toast")).toHaveText("You do not have access to this page.");
    }
    expect(adminResponses).toEqual([]);
    expect(problems).toEqual([]);

    // Un administrateur, lui, voit les liens.
    const context = await browser.newContext({ baseURL });
    try {
      const adminPage = await context.newPage();
      await signInAsAdmin(adminPage, admin);
      const adminNav = adminPage.getByRole("navigation", { name: "Main" });
      await expect(adminNav.getByRole("link", { name: "Predict" })).toBeVisible();
      await expect(adminNav.getByRole("link", { name: "Users" })).toBeVisible();
      await expect(adminNav.getByRole("link", { name: "Audit log" })).toBeVisible();
    } finally {
      await context.close();
    }
  });

  test("E2E-ISO-07 every admin route answers 403 to a marketer and 401 without a token", async ({
    page,
    request,
  }) => {
    const { marketerB } = getAccounts();
    const token = await captureAccessToken(page, marketerB);

    for (const [method, path] of ADMIN_API_ROUTES) {
      const forbidden = await request.fetch(path, {
        method,
        headers: { Authorization: `Bearer ${token}` },
        data: method === "GET" ? undefined : {},
      });
      expect(forbidden.status(), `${method} ${path} as marketer`).toBe(403);
      const body = (await forbidden.json()) as {
        error: { code: string; message: string; request_id: string };
      };
      expect(body.error.code).toBe("FORBIDDEN");
      expect(body.error.message).toBeTruthy();
      expect(body.error.request_id).toBeTruthy();

      const anonymous = await request.fetch(path, {
        method,
        data: method === "GET" ? undefined : {},
      });
      expect(anonymous.status(), `${method} ${path} without token`).toBe(401);
    }
  });
});

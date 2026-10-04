import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DataSummary } from "@/components/admin/data-summary";
import { ModelsView, errorRatio } from "@/components/admin/models-view";

import {
  activeModelFixture,
  apiErrorBody,
  metricsFixture,
  modelVersionFixture,
} from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const BASE = "http://localhost:3000/api/v1";
const ADMIN = `${BASE}/admin`;
const ACTIVE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const NEW_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

beforeEach(() => {
  vi.resetAllMocks();
  process.env.TZ = "UTC";
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

function figures(mae: number) {
  const metrics = metricsFixture();
  return {
    ...metrics,
    click_through_rate: { ...metrics.click_through_rate, mae },
    conversion_rate: { ...metrics.conversion_rate, mae },
    website_visits: { ...metrics.website_visits, mae: mae * 100 },
  };
}

/** v3 active (mean error 0.0733) and v4 succeeded, with the given mean error. */
function mockVersions(newMae = 0.07, extra: Record<string, unknown> = {}) {
  const active = modelVersionFixture({
    id: ACTIVE_ID,
    version: 3,
    is_active: true,
    metrics: figures(0.0733),
  });
  const fresh = modelVersionFixture({
    id: NEW_ID,
    version: 4,
    is_active: false,
    metrics: figures(newMae),
    created_at: "2026-10-05T09:12:00Z",
    ...extra,
  });
  server.use(
    http.get(`${ADMIN}/model-versions`, () => HttpResponse.json({ items: [fresh, active] })),
    http.get(`${ADMIN}/model-versions/${ACTIVE_ID}`, () => HttpResponse.json(active)),
    http.get(`${ADMIN}/model-versions/${NEW_ID}`, () => HttpResponse.json(fresh)),
    http.get(`${BASE}/model/active`, () =>
      HttpResponse.json(
        activeModelFixture({ id: ACTIVE_ID, version: 3, metrics: figures(0.0733) }),
      ),
    ),
    http.get(`${ADMIN}/dataset/summary`, () =>
      HttpResponse.json({ seed_rows: 8000, agency_rows: 0, holdout_rows: 1602 }),
    ),
  );
  return { active, fresh };
}

describe("DataSummary (Data page)", () => {
  function mockSummary() {
    server.use(
      http.get(`${ADMIN}/dataset/summary`, () =>
        HttpResponse.json({
          seed_rows: 8000,
          agency_rows: 0,
          holdout_rows: 1602,
          seed_loaded_at: "2026-10-03T23:50:00Z",
        }),
      ),
    );
  }

  it("shows the three tiles and the import of the starting dataset", async () => {
    mockSummary();
    renderWithClient(<DataSummary />, makeNoRetryClient());
    expect(screen.getByRole("heading", { level: 1, name: "Data" })).toBeTruthy();
    const tiles = within(await screen.findByTestId("data-tiles"));
    await tiles.findByText("8,000");
    expect(tiles.getByText("Starting dataset")).toBeTruthy();
    expect(tiles.getByText("Rows · synthetic, one person per row")).toBeTruthy();
    expect(tiles.getByText("Agency data")).toBeTruthy();
    expect(tiles.getByText("Rows · 250 needed for “Agency data only”")).toBeTruthy();
    expect(tiles.getByText("1,602")).toBeTruthy();
    expect(tiles.getByText("Rows never used for learning")).toBeTruthy();

    const row = screen.getByTestId("import-row");
    expect(Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent)).toEqual([
      "Oct 3, 2026, 23:50",
      "digital_marketing_campaign_dataset.csv",
      "Starting dataset",
      "8,000",
      "System",
      "Ready",
    ]);
  });

  it("is busy (skeleton tiles) while the totals load, and shows the API message on a failure", async () => {
    server.use(http.get(`${ADMIN}/dataset/summary`, () => new Promise(() => undefined)));
    const loading = renderWithClient(<DataSummary />, makeNoRetryClient());
    expect(loading.container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
    loading.unmount();

    server.use(
      http.get(`${ADMIN}/dataset/summary`, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<DataSummary />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Back-end is down.");
  });

  describe("Upload CSV dialog", () => {
    const HEADER =
      "CustomerID,Age,Gender,Income,CampaignChannel,CampaignType,AdSpend,ClickThroughRate,ConversionRate,WebsiteVisits,PagesPerVisit,TimeOnSite,SocialShares,EmailOpens,EmailClicks,PreviousPurchases,LoyaltyPoints,AdvertisingPlatform,AdvertisingTool,Conversion";
    const GOOD =
      "1,38,Female,65000,Email,Conversion,5000,0.15,0.1,24,5.4,7.6,50,11,5,3,2200,IsConfid,ToolConfid,1";
    const BAD =
      "2,17,F,65000,Email,Conversion,5000,4.2,0.1,24,5.4,7.6,50,11,5,3,2200,IsConfid,=cmd,1";

    async function openDialog() {
      mockSummary();
      renderWithClient(<DataSummary />, makeNoRetryClient());
      await within(await screen.findByTestId("data-tiles")).findByText("8,000");
      await userEvent.click(screen.getByRole("button", { name: "Upload CSV" }));
      return within(screen.getByRole("dialog", { name: "Upload agency data" }));
    }
    const csv = (name: string, content: string) => new File([content], name, { type: "text/csv" });

    it("explains the format, then asks for a file, a CSV, and the anonymization confirmation", async () => {
      const dialog = await openDialog();
      expect(dialog.getByText(/Amounts must be in USD\./)).toBeTruthy();
      expect(
        dialog.getByText("CSV, same columns as the starting dataset · 10 MB max"),
      ).toBeTruthy();
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe("Choose a CSV file.");

      await userEvent.upload(dialog.getByTestId("csv-file"), csv("notes.txt", "x"), {
        applyAccept: false,
      });
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe("Only CSV files are accepted.");

      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${GOOD}`),
      );
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe(
        "Confirm that client names are anonymized in this file.",
      );
    });

    it("lists the browser check problems by row and column and says nothing was imported", async () => {
      const dialog = await openDialog();
      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${GOOD}\n${BAD}`),
      );
      await userEvent.click(dialog.getByRole("checkbox"));
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe("The file contains 4 errors.");
      const rows = dialog
        .getAllByRole("row")
        .slice(1)
        .map((row) => Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent));
      expect(rows).toEqual([
        ["3", "Age", "Must be between 18 and 100."],
        ["3", "Gender", "Unknown value “F”. Expected Male or Female."],
        ["3", "ClickThroughRate", "Must be a fraction between 0 and 1 (got 4.2)."],
        ["3", "AdvertisingTool", "Cell starts with “=”; formulas are not allowed."],
      ]);
      expect(
        dialog.getByText("Nothing was imported. Fix the file and upload it again."),
      ).toBeTruthy();
    });

    it("uploads a valid file, then confirms with a toast, closes and refreshes the totals", async () => {
      let uploaded = "";
      let rows = 0;
      server.use(
        http.post(`${ADMIN}/dataset/upload`, async ({ request }) => {
          // The multipart body itself cannot be read back under jsdom (the stream never ends): the live check does it.
          uploaded = request.headers.get("content-type") ?? "";
          rows = 400;
          return HttpResponse.json({ rows_imported: 400, agency_rows_total: 400 }, { status: 201 });
        }),
      );
      const dialog = await openDialog();
      server.use(
        http.get(`${ADMIN}/dataset/summary`, () =>
          HttpResponse.json({
            seed_rows: 8000,
            agency_rows: rows,
            holdout_rows: 1602,
            seed_loaded_at: "2026-10-03T23:50:00Z",
            agency_loaded_at: "2026-10-05T09:00:00Z",
          }),
        ),
      );
      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${GOOD}`),
      );
      await userEvent.click(dialog.getByRole("checkbox"));
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await screen.findByTestId("toast")).textContent).toBe("400 rows imported.");
      expect(uploaded).toContain("multipart/form-data");
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      const tiles = within(screen.getByTestId("data-tiles"));
      expect(await tiles.findByText("400")).toBeTruthy();
      expect(tiles.getByText("Rows · enough for “Agency data only”")).toBeTruthy();
      const imports = screen.getAllByTestId("import-row");
      expect(imports).toHaveLength(2);
      expect(imports[1]?.textContent).toContain("Agency uploads");
    });

    it("does not send a file the browser check refuses", async () => {
      let called = false;
      server.use(
        http.post(`${ADMIN}/dataset/upload`, () => {
          called = true;
          return HttpResponse.json({}, { status: 201 });
        }),
      );
      const dialog = await openDialog();
      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${BAD}`),
      );
      await userEvent.click(dialog.getByRole("checkbox"));
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      await dialog.findByText("The file contains 4 errors.");
      expect(called).toBe(false);
    });

    it("lists the problems found by the API in the same table", async () => {
      server.use(
        http.post(`${ADMIN}/dataset/upload`, () =>
          HttpResponse.json(
            {
              error: {
                code: "CSV_INVALID",
                message: "The file contains 1 error.",
                details: [
                  {
                    row: 2,
                    column: "CustomerID",
                    issue: "invalid",
                    message: "Campaign number 1 was already imported.",
                  },
                ],
                request_id: "req-1",
              },
            },
            { status: 422 },
          ),
        ),
      );
      const dialog = await openDialog();
      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${GOOD}`),
      );
      await userEvent.click(dialog.getByRole("checkbox"));
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe("The file contains 1 error.");
      const rows = dialog
        .getAllByRole("row")
        .slice(1)
        .map((row) => Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent));
      expect(rows).toEqual([["2", "CustomerID", "Campaign number 1 was already imported."]]);
      expect(screen.queryByTestId("toast")).toBeNull();
    });

    it("shows the message of the API when the file was already imported", async () => {
      server.use(
        http.post(`${ADMIN}/dataset/upload`, () =>
          HttpResponse.json(
            apiErrorBody("DUPLICATE_UPLOAD", "This file has already been imported."),
            { status: 409 },
          ),
        ),
      );
      const dialog = await openDialog();
      await userEvent.upload(
        dialog.getByTestId("csv-file"),
        csv("agency.csv", `${HEADER}\n${GOOD}`),
      );
      await userEvent.click(dialog.getByRole("checkbox"));
      await userEvent.click(dialog.getByRole("button", { name: "Upload" }));
      expect((await dialog.findByRole("alert")).textContent).toBe(
        "This file has already been imported.",
      );
      expect(dialog.queryByRole("table")).toBeNull();
    });

    it("closes with Cancel", async () => {
      const dialog = await openDialog();
      await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });
});

describe("ModelsView (Models page)", () => {
  it("lists the versions with status and Active tags and selects the active one", async () => {
    mockVersions();
    renderWithClient(<ModelsView />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("model-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("v4");
    expect(rows[1]?.textContent).toContain("v3");
    expect(rows[1]?.textContent).toContain("Active");
    expect(rows[1]?.textContent).toContain("All data");
    expect(rows[1]?.textContent).toContain("E2E Admin");
    expect(rows[1]?.textContent).toContain("Review");
    expect(rows[1]?.getAttribute("aria-selected")).toBe("true");
    const detail = within(await screen.findByTestId("model-detail"));
    expect(detail.getByRole("heading", { name: "Version v3" })).toBeTruthy();
    expect(
      detail.getByText("This is the active version. Every new prediction uses it."),
    ).toBeTruthy();
    expect(detail.queryByRole("button", { name: "Activate this version" })).toBeNull();
  });

  it("compares a succeeded version with the active one, then activates it with a toast", async () => {
    mockVersions(0.07);
    let activated = false;
    server.use(
      http.post(`${ADMIN}/model-versions/${NEW_ID}/activate`, () => {
        activated = true;
        return HttpResponse.json({ ok: true });
      }),
    );
    renderWithClient(<ModelsView />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("model-row");
    await userEvent.click(rows[0] as HTMLElement);
    const table = within(await screen.findByTestId("compare-table"));
    expect(table.getByText("v3")).toBeTruthy();
    expect(table.getByText("v4")).toBeTruthy();
    const cells = table
      .getAllByRole("row")
      .slice(1)
      .map((row) => Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent));
    expect(cells).toEqual([
      ["Click-through rate", "0.0733", "0.0700", "-4.50%"],
      ["Conversion rate", "0.0733", "0.0700", "-4.50%"],
      ["Website visits", "7.33", "7.00", "-4.50%"],
    ]);
    expect((await screen.findByTestId("verdict")).textContent).toBe(
      "At least as reliable as the active version",
    );
    await userEvent.click(screen.getByRole("button", { name: "Activate this version" }));
    await waitFor(() => expect(activated).toBe(true));
    expect((await screen.findByTestId("toast")).textContent).toBe("Model v4 is now active.");
  });

  it("shows the verdict 'less reliable' and keeps the activate button disabled", async () => {
    mockVersions(0.09);
    renderWithClient(<ModelsView />, makeNoRetryClient());
    await userEvent.click((await screen.findAllByTestId("model-row"))[0] as HTMLElement);
    expect((await screen.findByTestId("verdict")).textContent).toBe(
      "Less reliable than the active version",
    );
    expect(
      (screen.getByRole("button", { name: "Activate this version" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.getAllByText("+22.78%")).toHaveLength(3);
  });

  it("says there is nothing to compare against when no version is active", async () => {
    const { fresh } = mockVersions();
    server.use(
      http.get(`${ADMIN}/model-versions`, () => HttpResponse.json({ items: [fresh] })),
      http.get(`${BASE}/model/active`, () =>
        HttpResponse.json(apiErrorBody("NO_ACTIVE_MODEL", "No model is active."), { status: 409 }),
      ),
    );
    renderWithClient(<ModelsView />, makeNoRetryClient());
    expect(await screen.findByText("No active version to compare against.")).toBeTruthy();
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: "Activate this version" }) as HTMLButtonElement)
          .disabled,
      ).toBe(false),
    );
  });

  it("shows the progress of a queued or running version and the reason of a failure", async () => {
    mockVersions(0.07, { status: "running", metrics: null });
    renderWithClient(<ModelsView initialId={NEW_ID} />, makeNoRetryClient());
    expect(
      await screen.findByText("Running. Training three models and testing on held-out rows…"),
    ).toBeTruthy();
    expect(screen.getByTestId("model-status").textContent).toBe("Running");
  });

  it("shows the error message of a failed version", async () => {
    mockVersions(0.07, {
      status: "failed",
      metrics: null,
      error_message: "Training was interrupted.",
    });
    renderWithClient(<ModelsView initialId={NEW_ID} />, makeNoRetryClient());
    expect(await screen.findByText("Training was interrupted.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Activate this version" })).toBeNull();
  });

  it("says so when no version exists yet", async () => {
    server.use(http.get(`${ADMIN}/model-versions`, () => HttpResponse.json({ items: [] })));
    renderWithClient(<ModelsView />, makeNoRetryClient());
    expect(await screen.findByText("No version yet. Train the first one.")).toBeTruthy();
  });

  it("is busy while the versions load and shows the API message on a failure", async () => {
    server.use(http.get(`${ADMIN}/model-versions`, () => new Promise(() => undefined)));
    const loading = renderWithClient(<ModelsView />, makeNoRetryClient());
    expect(loading.container.querySelector('[aria-busy="true"]')).not.toBeNull();
    loading.unmount();
    server.use(
      http.get(`${ADMIN}/model-versions`, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<ModelsView />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Back-end is down.");
  });

  describe("Train a new version dialog", () => {
    it("offers all data, keeps 'Agency data only' disabled below 250 agency rows, and starts the training", async () => {
      mockVersions();
      let body: unknown = null;
      server.use(
        http.post(`${ADMIN}/model-versions`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(modelVersionFixture({ id: NEW_ID, status: "queued" }), {
            status: 202,
          });
        }),
      );
      renderWithClient(<ModelsView />, makeNoRetryClient());
      await screen.findAllByTestId("model-row");
      await userEvent.click(screen.getByRole("button", { name: "Train a new version" }));
      const dialog = within(screen.getByRole("dialog", { name: "Train a new version" }));
      expect(dialog.getByText(/Trains three models \(one per figure\)/)).toBeTruthy();
      expect((dialog.getByLabelText(/All data/) as HTMLInputElement).checked).toBe(true);
      expect((dialog.getByLabelText("Agency data only") as HTMLInputElement).disabled).toBe(true);
      expect(dialog.getByText("Requires at least 250 agency rows.")).toBeTruthy();
      await userEvent.click(dialog.getByRole("button", { name: "Start training" }));
      await waitFor(() => expect(body).toEqual({ data_scope: "all" }));
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    });

    it("enables 'Agency data only' from 250 agency rows and sends that scope", async () => {
      mockVersions();
      server.use(
        http.get(`${ADMIN}/dataset/summary`, () =>
          HttpResponse.json({ seed_rows: 8000, agency_rows: 400, holdout_rows: 1700 }),
        ),
      );
      let body: unknown = null;
      server.use(
        http.post(`${ADMIN}/model-versions`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(
            modelVersionFixture({ id: NEW_ID, status: "queued", data_scope: "agency_only" }),
            { status: 202 },
          );
        }),
      );
      renderWithClient(<ModelsView />, makeNoRetryClient());
      await screen.findAllByTestId("model-row");
      await userEvent.click(screen.getByRole("button", { name: "Train a new version" }));
      const dialog = within(screen.getByRole("dialog", { name: "Train a new version" }));
      const agency = dialog.getByLabelText("Agency data only") as HTMLInputElement;
      await waitFor(() => expect(agency.disabled).toBe(false));
      expect(dialog.queryByText("Requires at least 250 agency rows.")).toBeNull();
      await userEvent.click(agency);
      expect(agency.checked).toBe(true);
      await userEvent.click(dialog.getByRole("button", { name: "Start training" }));
      await waitFor(() => expect(body).toEqual({ data_scope: "agency_only" }));
    });

    it("tells with a toast when a training is already running", async () => {
      mockVersions();
      server.use(
        http.post(`${ADMIN}/model-versions`, () =>
          HttpResponse.json(
            apiErrorBody("TRAINING_ALREADY_RUNNING", "A training run is already in progress."),
            { status: 409 },
          ),
        ),
      );
      renderWithClient(<ModelsView />, makeNoRetryClient());
      await screen.findAllByTestId("model-row");
      await userEvent.click(screen.getByRole("button", { name: "Train a new version" }));
      await userEvent.click(screen.getByRole("button", { name: "Start training" }));
      expect((await screen.findByTestId("toast")).textContent).toBe(
        "A training run is already in progress.",
      );
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("shows other API errors inside the dialog", async () => {
      mockVersions();
      server.use(
        http.post(`${ADMIN}/model-versions`, () =>
          HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
            status: 503,
          }),
        ),
      );
      renderWithClient(<ModelsView />, makeNoRetryClient());
      await screen.findAllByTestId("model-row");
      await userEvent.click(screen.getByRole("button", { name: "Train a new version" }));
      await userEvent.click(screen.getByRole("button", { name: "Start training" }));
      expect((await within(screen.getByRole("dialog")).findByRole("alert")).textContent).toContain(
        "Back-end is down.",
      );
    });
  });
});

describe("errorRatio", () => {
  type Metrics = Parameters<typeof errorRatio>[0];
  const metrics = (mae: number) => figures(mae) as unknown as Metrics;

  it("is 1 for identical errors, below 1 when better and above 1 when worse", () => {
    expect(errorRatio(metrics(0.0733), metrics(0.0733))).toBeCloseTo(1);
    expect(errorRatio(metrics(0.07), metrics(0.0733))).toBeLessThan(1);
    expect(errorRatio(metrics(0.09), metrics(0.0733))).toBeGreaterThan(1);
  });
});

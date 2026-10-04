/**
 * `AuditTable` (client) : journal d'audit en lecture seule (PRD US-05).
 * Colonnes : Date, Author, Action, Target, Details ; lignes `data-testid="audit-row"`,
 * code d'action dans `data-testid="audit-action"`.
 */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuditTable } from "@/components/admin/audit-table";

import {
  adminUserFixture,
  adminUsersPage,
  apiErrorBody,
  auditEntryFixture,
  auditPage,
  modelVersionFixture,
} from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const AUDIT_URL = "http://localhost:3000/api/v1/admin/audit-log";
const VERSIONS_URL = "http://localhost:3000/api/v1/admin/model-versions";
const USERS_URL = "http://localhost:3000/api/v1/admin/users";
const VERSION_ID = "22222222-2222-4222-8222-222222222222";
const OLD_VERSION_ID = "33333333-3333-4333-8333-333333333333";

function cells(row: HTMLElement): HTMLElement[] {
  return Array.from(row.querySelectorAll("td"));
}

describe("AuditTable", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
    // The target names come from the users and the versions (one request each, in parallel).
    server.use(
      http.get(VERSIONS_URL, () =>
        HttpResponse.json({
          items: [
            modelVersionFixture({ id: VERSION_ID, version: 3 }),
            modelVersionFixture({ id: OLD_VERSION_ID, version: 1 }),
          ],
        }),
      ),
      http.get(USERS_URL, () =>
        HttpResponse.json(
          adminUsersPage([
            adminUserFixture({
              id: "11111111-1111-4111-8111-111111111111",
              full_name: "Ada Lovelace",
            }),
          ]),
        ),
      ),
    );
  });

  it("shows the five column headers of PRD US-05", async () => {
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([auditEntryFixture()]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    await screen.findAllByTestId("audit-row");
    expect(screen.getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Date",
      "Author",
      "Action",
      "Target",
      "Details",
    ]);
  });

  it("shows the date like the prototype, the author's name and the action code", async () => {
    process.env.TZ = "UTC";
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([auditEntryFixture()]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    const [date, author] = cells(row as HTMLElement);
    expect(date?.textContent).toBe("Oct 3, 2026, 14:05");
    expect(author?.textContent).toBe("E2E Admin");
    expect(within(row as HTMLElement).getByTestId("audit-action").textContent).toBe("user.invited");
  });

  it("shows 'System' when there is no actor", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([auditEntryFixture({ actor: null, action: "model.training_succeeded" })]),
        ),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    expect(cells(row as HTMLElement)[1]?.textContent).toBe("System");
  });

  it("shows the user's full name as the target, never the raw id", async () => {
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([auditEntryFixture()]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    const target = cells(row as HTMLElement)[3];
    expect(target?.textContent).toBe("Ada Lovelace");
    expect(target?.textContent).not.toContain("11111111-1111-4111-8111-111111111111");
  });

  it("falls back to the e-mail of the metadata when the user is not in the list", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(auditPage([auditEntryFixture({ target_id: "gone-user" })])),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    expect(cells(row as HTMLElement)[3]?.textContent).toBe("ada@example.test");
  });

  it("shows 'Model v3' for a model version and the file name or id for an upload", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({
              id: 2,
              action: "model.activated",
              target_type: "model_version",
              target_id: VERSION_ID,
              metadata: {},
            }),
            auditEntryFixture({
              id: 1,
              action: "upload.accepted",
              target_type: "upload",
              target_id: "9f9f9f9f-0000-4000-8000-000000000009",
              metadata: { rows: 8000 },
            }),
          ]),
        ),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("audit-row");
    expect(cells(rows[0] as HTMLElement)[3]?.textContent).toBe("Model v3");
    expect(cells(rows[1] as HTMLElement)[3]?.textContent).toBe(
      "9f9f9f9f-0000-4000-8000-000000000009",
    );
  });

  it.each([
    ["user.invited", { email: "ada@example.test", role: "marketer" }, "Role: marketer"],
    [
      "user.role_changed",
      { email: "ada@example.test", from: "marketer", to: "admin" },
      "marketer → admin",
    ],
    ["user.deactivated", { email: "ada@example.test" }, "—"],
    ["model.training_requested", { data_scope: "all" }, "Scope: all data"],
    [
      "model.training_succeeded",
      { train_rows: 6412, test_rows: 1588 },
      "6,412 training rows · 1,588 test rows",
    ],
    ["model.training_succeeded", {}, "—"],
    ["model.training_failed", { reason: "Training was interrupted." }, "Training was interrupted."],
  ])("writes the details of %s as a sentence", async (action, metadata, expected) => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(auditPage([auditEntryFixture({ action, metadata })])),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    expect(cells(row as HTMLElement)[4]?.textContent).toBe(expected);
  });

  it("says which version an activation replaced, or that it is the first", async () => {
    const activated = (id: number, versionId: string) =>
      auditEntryFixture({
        id,
        action: "model.activated",
        target_type: "model_version",
        target_id: versionId,
        metadata: {},
      });
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(auditPage([activated(2, VERSION_ID), activated(1, OLD_VERSION_ID)])),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("audit-row");
    expect(cells(rows[0] as HTMLElement)[4]?.textContent).toBe("Replaced v1");
    expect(cells(rows[1] as HTMLElement)[4]?.textContent).toBe("First active version");
  });

  it("renders metadata values and names as text, never as HTML (SEC-14)", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({
              actor: { id: "a", full_name: "<b>Mallory</b>" },
              target_id: "gone-user",
              metadata: { email: "<img src=x onerror=alert(1)>", role: "<i>admin</i>" },
            }),
          ]),
        ),
      ),
    );
    const { container } = renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    expect(cells(row as HTMLElement)[3]?.textContent).toBe("<img src=x onerror=alert(1)>");
    expect(cells(row as HTMLElement)[4]?.textContent).toBe("Role: <i>admin</i>");
    expect(cells(row as HTMLElement)[1]?.textContent).toBe("<b>Mallory</b>");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("i")).toBeNull();
  });

  it("keeps the order sent by the API (newest first)", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({ id: 3, action: "user.reactivated" }),
            auditEntryFixture({ id: 2, action: "user.deactivated" }),
            auditEntryFixture({ id: 1, action: "user.invited" }),
          ]),
        ),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    await screen.findAllByTestId("audit-row");
    expect(screen.getAllByTestId("audit-action").map((cell) => cell.textContent)).toEqual([
      "user.reactivated",
      "user.deactivated",
      "user.invited",
    ]);
  });

  it("shows 'No audit entries yet.' for an empty log", async () => {
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    expect(await screen.findByText("No audit entries yet.")).toBeTruthy();
    expect(screen.queryAllByTestId("audit-row")).toHaveLength(0);
  });

  it("is busy while the log loads", () => {
    server.use(http.get(AUDIT_URL, () => new Promise(() => undefined)));
    const { container } = renderWithClient(<AuditTable />, makeNoRetryClient());
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it("shows the API message in an alert when the log cannot be loaded", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Back-end is down.");
  });

  it("shows Load more while there is a next page, appends the next page, and hides the button at the end", async () => {
    const cursors: (string | null)[] = [];
    server.use(
      http.get(AUDIT_URL, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        cursors.push(cursor);
        return HttpResponse.json(
          cursor === null
            ? auditPage([auditEntryFixture({ id: 2, action: "user.deactivated" })], "audit-next")
            : auditPage([auditEntryFixture({ id: 1, action: "user.invited" })]),
        );
      }),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    await screen.findAllByTestId("audit-row");
    expect(screen.getAllByTestId("audit-row")).toHaveLength(1);
    await userEvent.setup().click(screen.getByRole("button", { name: "Load more" }));
    await screen.findByText("user.invited");
    expect(screen.getAllByTestId("audit-row")).toHaveLength(2);
    expect(cursors).toEqual([null, "audit-next"]);
    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
  });
});

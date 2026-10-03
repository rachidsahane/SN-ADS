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

import { apiErrorBody, auditEntryFixture, auditPage } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));

const AUDIT_URL = "http://localhost:3000/api/v1/admin/audit-log";

function cells(row: HTMLElement): HTMLElement[] {
  return Array.from(row.querySelectorAll("td"));
}

describe("AuditTable", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
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

  it("shows the date formatted in UTC, the author's name and the action code", async () => {
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([auditEntryFixture()]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    const [date, author] = cells(row as HTMLElement);
    expect(date?.textContent).toBe("2026-10-03 14:05 UTC");
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

  it("shows the target type and the e-mail from the metadata when present", async () => {
    server.use(http.get(AUDIT_URL, () => HttpResponse.json(auditPage([auditEntryFixture()]))));
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    const target = cells(row as HTMLElement)[3];
    expect(target?.textContent).toContain("user");
    expect(target?.textContent).toContain("ada@example.test");
    expect(target?.textContent).not.toContain("11111111-1111-4111-8111-111111111111");
  });

  it("falls back to the target id when the metadata has no e-mail", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({
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
    const [row] = await screen.findAllByTestId("audit-row");
    const target = cells(row as HTMLElement)[3];
    expect(target?.textContent).toContain("upload");
    expect(target?.textContent).toContain("9f9f9f9f-0000-4000-8000-000000000009");
  });

  it("shows the metadata as key: value pairs", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({
              action: "user.role_changed",
              metadata: { email: "ada@example.test", from: "marketer", to: "admin" },
            }),
          ]),
        ),
      ),
    );
    renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    const details = cells(row as HTMLElement)[4]?.textContent ?? "";
    expect(details).toContain("from: marketer");
    expect(details).toContain("to: admin");
  });

  it("renders metadata values and names as text, never as HTML (SEC-14)", async () => {
    server.use(
      http.get(AUDIT_URL, () =>
        HttpResponse.json(
          auditPage([
            auditEntryFixture({
              actor: { id: "a", full_name: "<b>Mallory</b>" },
              metadata: { note: "<img src=x onerror=alert(1)>" },
            }),
          ]),
        ),
      ),
    );
    const { container } = renderWithClient(<AuditTable />, makeNoRetryClient());
    const [row] = await screen.findAllByTestId("audit-row");
    expect(cells(row as HTMLElement)[4]?.textContent).toContain(
      "note: <img src=x onerror=alert(1)>",
    );
    expect(cells(row as HTMLElement)[1]?.textContent).toBe("<b>Mallory</b>");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
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

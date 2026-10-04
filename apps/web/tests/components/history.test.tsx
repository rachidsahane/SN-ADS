import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HistoryTable } from "@/components/history/history-table";

import { apiErrorBody } from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

const BASE = "http://localhost:3000/api/v1/predictions";
const ID = "33333333-3333-4333-8333-333333333333";
const ID2 = "44444444-4444-4444-8444-444444444444";

function item(overrides: Record<string, unknown> = {}) {
  return {
    id: ID,
    name: "Spring push",
    created_at: "2026-10-04T10:30:00Z",
    level: "medium",
    model_version: 3,
    campaign_channel: "Email",
    campaign_type: "Conversion",
    score: 51.04,
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  process.env.TZ = "UTC";
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("HistoryTable (prototype table)", () => {
  it("lists name, date, channel, type, level tag, score and model with a link to the saved prediction", async () => {
    server.use(http.get(BASE, () => HttpResponse.json({ items: [item()] })));
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    const row = await screen.findByTestId("history-row");
    const cells = Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent);
    expect(cells).toEqual([
      "Spring push",
      "Oct 4, 2026, 10:30",
      "Email",
      "Conversion",
      "Medium",
      "51.0",
      "v3",
      "",
    ]);
    expect(screen.getByRole("link", { name: "Spring push" }).getAttribute("href")).toBe(
      `/history/${ID}`,
    );
    expect(within(row).getByText("Medium").className).toContain("tag-accent");
  });

  it("uses a different tag style per level (Low neutral, Medium accent, High outline)", async () => {
    server.use(
      http.get(BASE, () =>
        HttpResponse.json({
          items: [item({ level: "low" }), item({ id: ID2, level: "high" })],
        }),
      ),
    );
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    await screen.findAllByTestId("history-row");
    expect(screen.getByText("Low").className).toContain("tag-neutral");
    expect(screen.getByText("High").className).toContain("tag-outline");
  });

  it("says so when nothing is saved yet", async () => {
    server.use(http.get(BASE, () => HttpResponse.json({ items: [] })));
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    expect(
      await screen.findByText(
        "No saved predictions yet. Use “Save prediction” on the Predict page.",
      ),
    ).toBeTruthy();
  });

  it("is busy while loading and shows the API message on a failure", async () => {
    server.use(http.get(BASE, () => new Promise(() => undefined)));
    const loading = renderWithClient(<HistoryTable />, makeNoRetryClient());
    expect(loading.container.querySelector('[aria-busy="true"]')).not.toBeNull();
    loading.unmount();

    server.use(
      http.get(BASE, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toContain("Back-end is down.");
  });

  it("asks for a confirmation in the row, then deletes and confirms with a toast", async () => {
    let deleted: string | null = null;
    let items = [item(), item({ id: ID2, name: "Other" })];
    server.use(
      http.get(BASE, () => HttpResponse.json({ items })),
      http.delete(`${BASE}/:id`, ({ params }) => {
        deleted = String(params.id);
        items = items.filter((entry) => entry.id !== params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    const rows = await screen.findAllByTestId("history-row");
    await userEvent.click(
      within(rows[0] as HTMLElement).getByRole("button", { name: "Delete prediction" }),
    );
    expect(within(rows[0] as HTMLElement).getByText("Delete?")).toBeTruthy();
    expect(deleted).toBeNull();

    // Cancel puts the trash icon back.
    await userEvent.click(within(rows[0] as HTMLElement).getByRole("button", { name: "Cancel" }));
    expect(within(rows[0] as HTMLElement).queryByText("Delete?")).toBeNull();

    await userEvent.click(
      within(rows[0] as HTMLElement).getByRole("button", { name: "Delete prediction" }),
    );
    await userEvent.click(within(rows[0] as HTMLElement).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleted).toBe(ID));
    expect((await screen.findByTestId("toast")).textContent).toBe("Prediction deleted.");
    await waitFor(() => expect(screen.getAllByTestId("history-row")).toHaveLength(1));
  });

  it("shows the API message when a deletion fails and keeps the row", async () => {
    server.use(
      http.get(BASE, () => HttpResponse.json({ items: [item()] })),
      http.delete(`${BASE}/:id`, () =>
        HttpResponse.json(apiErrorBody("NOT_FOUND", "Prediction not found."), { status: 404 }),
      ),
    );
    renderWithClient(<HistoryTable />, makeNoRetryClient());
    const row = await screen.findByTestId("history-row");
    await userEvent.click(within(row).getByRole("button", { name: "Delete prediction" }));
    await userEvent.click(within(row).getByRole("button", { name: "Delete" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Prediction not found.");
    expect(screen.getAllByTestId("history-row")).toHaveLength(1);
  });
});

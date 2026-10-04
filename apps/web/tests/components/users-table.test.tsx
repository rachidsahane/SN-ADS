/**
 * `UsersTable` (client) : tableau des utilisateurs, actions de rôle et d'activation, bouton « Invite user ».
 * Il lit le profil (`useMe`) pour reconnaître la ligne de l'appelant, et la liste (`useAdminUsers`).
 * Les mutations passent par `PATCH /api/v1/admin/users/{id}` (corps limité aux clés modifiées).
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UsersTable } from "@/components/admin/users-table";
import { labels } from "@/lib/labels";

import {
  ADMIN_ID,
  adminMeFixture,
  adminUserFixture,
  adminUsersPage,
  apiErrorBody,
} from "../helpers/fixtures";
import { makeNoRetryClient, renderWithClient } from "../helpers/render";
import { server } from "../msw/server";

const auth = vi.hoisted(() => ({ getSession: vi.fn(), signOut: vi.fn() }));
vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/admin/users",
  useSearchParams: () => new URLSearchParams(""),
}));

const BASE = "http://localhost:3000";
const ME_URL = `${BASE}/api/v1/me`;
const USERS_URL = `${BASE}/api/v1/admin/users`;

const ADA = adminUserFixture();
const BOB = adminUserFixture({
  id: "22222222-2222-4222-8222-222222222222",
  email: "bob@example.test",
  full_name: "Bob Builder",
  role: "admin",
  status: "active",
});
const CARA = adminUserFixture({
  id: "33333333-3333-4333-8333-333333333333",
  email: "cara@example.test",
  full_name: "Cara Off",
  is_active: false,
  status: "deactivated",
});
const DAN = adminUserFixture({
  id: "44444444-4444-4444-8444-444444444444",
  email: "dan@example.test",
  full_name: "Dan Pending",
  status: "invited",
});
const SELF = adminUserFixture({
  id: ADMIN_ID,
  email: "e2e-admin@example.test",
  full_name: "E2E Admin",
  role: "admin",
  status: "active",
});

function useList(items: unknown[], nextCursor: string | null = null) {
  server.use(http.get(USERS_URL, () => HttpResponse.json(adminUsersPage(items, nextCursor))));
}

function rowOf(email: string): HTMLElement {
  const row = screen
    .getAllByTestId("user-row")
    .find((candidate) => candidate.textContent?.includes(email));
  if (!row) {
    throw new Error(`no row for ${email}`);
  }
  return row;
}

describe("UsersTable", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
    server.use(http.get(ME_URL, () => HttpResponse.json(adminMeFixture())));
  });

  describe("display", () => {
    it("shows the five column headers of the Users page", async () => {
      useList([ADA]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      const headers = screen.getAllByRole("columnheader").map((header) => header.textContent);
      expect(headers).toEqual(["Name", "Email", "Role", "Status", ""]);
    });

    it("shows one data-testid=user-row per user with name, e-mail and role select", async () => {
      useList([ADA, BOB]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      expect(screen.getAllByTestId("user-row")).toHaveLength(2);
      const ada = rowOf("ada@example.test");
      expect(within(ada).getByText("Ada Lovelace")).toBeTruthy();
      expect(within(ada).getByText("ada@example.test")).toBeTruthy();
      const roleOfAda = within(ada).getByLabelText(
        "Role for ada@example.test",
      ) as HTMLSelectElement;
      expect(roleOfAda.value).toBe("marketer");
      const roleOfBob = within(rowOf("bob@example.test")).getByLabelText(
        "Role for bob@example.test",
      ) as HTMLSelectElement;
      expect(roleOfBob.value).toBe("admin");
    });

    it("offers exactly the Marketer and Admin options in the role select", async () => {
      useList([ADA]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      const select = screen.getByLabelText("Role for ada@example.test") as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => [option.value, option.text])).toEqual([
        ["marketer", "Marketer"],
        ["admin", "Admin"],
      ]);
    });

    it("shows the status labels Invited, Active and Deactivated in data-testid=user-status", async () => {
      useList([ADA, CARA, DAN]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      const status = (email: string) => within(rowOf(email)).getByTestId("user-status").textContent;
      expect(status("ada@example.test")).toBe("Active");
      expect(status("cara@example.test")).toBe("Deactivated");
      expect(status("dan@example.test")).toBe("Invited");
    });

    it("offers Deactivate for an active or invited user and Reactivate for a deactivated one", async () => {
      useList([ADA, CARA, DAN]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      expect(
        within(rowOf("ada@example.test")).getByRole("button", { name: "Deactivate" }),
      ).toBeTruthy();
      expect(
        within(rowOf("dan@example.test")).getByRole("button", { name: "Deactivate" }),
      ).toBeTruthy();
      const cara = within(rowOf("cara@example.test"));
      expect(cara.getByRole("button", { name: "Reactivate" })).toBeTruthy();
      expect(cara.queryByRole("button", { name: "Deactivate" })).toBeNull();
    });

    it("renders names and e-mails as text, never as HTML (SEC-14)", async () => {
      const hostile = "<img src=x onerror=alert(1)>";
      useList([adminUserFixture({ full_name: hostile })]);
      const { container } = renderWithClient(<UsersTable />, makeNoRetryClient());
      expect(await screen.findByText(hostile)).toBeTruthy();
      expect(container.querySelector("img")).toBeNull();
    });
  });

  describe("states", () => {
    it("is busy while the list loads", () => {
      server.use(http.get(USERS_URL, () => new Promise(() => undefined)));
      const { container } = renderWithClient(<UsersTable />, makeNoRetryClient());
      expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
      expect(screen.queryAllByTestId("user-row")).toHaveLength(0);
    });

    it("shows 'No users yet.' for an empty list", async () => {
      useList([]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      expect(await screen.findByText("No users yet.")).toBeTruthy();
      expect(screen.queryAllByTestId("user-row")).toHaveLength(0);
    });

    it("shows the API message in an alert when the list cannot be loaded", async () => {
      server.use(
        http.get(USERS_URL, () =>
          HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
            status: 503,
          }),
        ),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      const alert = await screen.findByRole("alert");
      expect(alert.textContent).toContain("Back-end is down.");
    });
  });

  describe("the caller's own row", () => {
    it("shows the You badge and disables the role select and the Deactivate button, with the hint as title", async () => {
      useList([SELF, ADA]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      const own = within(rowOf("e2e-admin@example.test"));
      expect(own.getByText("(you)")).toBeTruthy();
      const select = own.getByLabelText("Role for e2e-admin@example.test") as HTMLSelectElement;
      const button = own.getByRole("button", { name: "Deactivate" }) as HTMLButtonElement;
      expect(select.disabled).toBe(true);
      expect(button.disabled).toBe(true);
      expect(select.getAttribute("title")).toBe("You cannot change your own account.");
      expect(button.getAttribute("title")).toBe("You cannot change your own account.");
    });

    it("shows no You badge and keeps the controls enabled on the other rows", async () => {
      useList([SELF, ADA]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      const other = within(rowOf("ada@example.test"));
      expect(other.queryByText("You")).toBeNull();
      expect(
        (other.getByLabelText("Role for ada@example.test") as HTMLSelectElement).disabled,
      ).toBe(false);
      expect(
        (other.getByRole("button", { name: "Deactivate" }) as HTMLButtonElement).disabled,
      ).toBe(false);
    });
  });

  describe("actions", () => {
    it("sends PATCH {role} at once when the role select changes", async () => {
      useList([ADA]);
      let received: unknown = null;
      let patchedUrl = "";
      server.use(
        http.patch(`${USERS_URL}/:id`, async ({ request }) => {
          patchedUrl = new URL(request.url).pathname;
          received = await request.json();
          return HttpResponse.json({ ...ADA, role: "admin" });
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      await userEvent
        .setup()
        .selectOptions(screen.getByLabelText("Role for ada@example.test"), "admin");
      await waitFor(() => expect(received).not.toBeNull());
      expect(received).toEqual({ role: "admin" });
      expect(patchedUrl).toBe(`/api/v1/admin/users/${ADA.id}`);
    });

    it("sends PATCH {is_active: false} when Deactivate is clicked on an active user", async () => {
      useList([ADA]);
      let received: unknown = null;
      server.use(
        http.patch(`${USERS_URL}/:id`, async ({ request }) => {
          received = await request.json();
          return HttpResponse.json({ ...ADA, is_active: false, status: "deactivated" });
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      await userEvent.setup().click(screen.getByRole("button", { name: "Deactivate" }));
      await waitFor(() => expect(received).not.toBeNull());
      expect(received).toEqual({ is_active: false });
    });

    it("sends PATCH {is_active: true} when Reactivate is clicked on a deactivated user", async () => {
      useList([CARA]);
      let received: unknown = null;
      server.use(
        http.patch(`${USERS_URL}/:id`, async ({ request }) => {
          received = await request.json();
          return HttpResponse.json({ ...CARA, is_active: true, status: "active" });
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Cara Off");
      await userEvent.setup().click(screen.getByRole("button", { name: "Reactivate" }));
      await waitFor(() => expect(received).not.toBeNull());
      expect(received).toEqual({ is_active: true });
    });

    it("reloads the list after a successful action and shows the new status", async () => {
      let deactivated = false;
      server.use(
        http.get(USERS_URL, () =>
          HttpResponse.json(
            adminUsersPage([
              deactivated ? { ...ADA, is_active: false, status: "deactivated" } : ADA,
            ]),
          ),
        ),
        http.patch(`${USERS_URL}/:id`, () => {
          deactivated = true;
          return HttpResponse.json({ ...ADA, is_active: false, status: "deactivated" });
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      await userEvent.setup().click(screen.getByRole("button", { name: "Deactivate" }));
      await waitFor(() =>
        expect(within(rowOf("ada@example.test")).getByTestId("user-status").textContent).toBe(
          "Deactivated",
        ),
      );
      expect(
        within(rowOf("ada@example.test")).getByRole("button", { name: "Reactivate" }),
      ).toBeTruthy();
    });

    it("disables the controls of the row while its request is pending, then re-enables them", async () => {
      useList([ADA, BOB]);
      let release: () => void = () => undefined;
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      server.use(
        http.patch(`${USERS_URL}/:id`, async () => {
          await gate;
          return HttpResponse.json({ ...ADA, is_active: false, status: "deactivated" });
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      await userEvent
        .setup()
        .click(within(rowOf("ada@example.test")).getByRole("button", { name: "Deactivate" }));
      const ada = within(rowOf("ada@example.test"));
      await waitFor(() => {
        expect(
          (ada.getByLabelText("Role for ada@example.test") as HTMLSelectElement).disabled,
        ).toBe(true);
        expect((ada.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
      });
      // La ligne voisine reste utilisable.
      expect(
        (
          within(rowOf("bob@example.test")).getByLabelText(
            "Role for bob@example.test",
          ) as HTMLSelectElement
        ).disabled,
      ).toBe(false);
      release();
      await waitFor(() =>
        expect(
          (
            within(rowOf("ada@example.test")).getByLabelText(
              "Role for ada@example.test",
            ) as HTMLSelectElement
          ).disabled,
        ).toBe(false),
      );
    });

    it("shows the API message of a 409 LAST_ADMIN in an alert, and the select returns to the server value", async () => {
      useList([BOB]);
      server.use(
        http.patch(`${USERS_URL}/:id`, () =>
          HttpResponse.json(
            apiErrorBody("LAST_ADMIN", "At least one active administrator is required."),
            { status: 409 },
          ),
        ),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Bob Builder");
      await userEvent
        .setup()
        .selectOptions(screen.getByLabelText("Role for bob@example.test"), "marketer");
      const alert = await screen.findByRole("alert");
      expect(alert.textContent).toContain("At least one active administrator is required.");
      await waitFor(() =>
        expect(
          (screen.getByLabelText("Role for bob@example.test") as HTMLSelectElement).value,
        ).toBe("admin"),
      );
    });

    it.each([
      ["SELF_ACTION_FORBIDDEN", 409, "You cannot change your own account."],
      ["NOT_FOUND", 404, "User not found."],
      ["SERVICE_UNAVAILABLE", 503, labels.errors.serviceUnavailable],
    ])(
      "shows the API message of a %s answer (%s) in the table alert",
      async (code, status, message) => {
        useList([ADA]);
        server.use(
          http.patch(`${USERS_URL}/:id`, () =>
            HttpResponse.json(apiErrorBody(code, message), { status }),
          ),
        );
        renderWithClient(<UsersTable />, makeNoRetryClient());
        await screen.findByText("Ada Lovelace");
        await userEvent.setup().click(screen.getByRole("button", { name: "Deactivate" }));
        expect((await screen.findByRole("alert")).textContent).toContain(message);
      },
    );
  });

  describe("pagination", () => {
    it("shows Load more while there is a next page, fetches it with the cursor, and hides the button at the end", async () => {
      const cursors: (string | null)[] = [];
      server.use(
        http.get(USERS_URL, ({ request }) => {
          const cursor = new URL(request.url).searchParams.get("cursor");
          cursors.push(cursor);
          return HttpResponse.json(
            cursor === null ? adminUsersPage([ADA], "next-1") : adminUsersPage([BOB]),
          );
        }),
      );
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      expect(screen.queryByText("Bob Builder")).toBeNull();
      await userEvent.setup().click(screen.getByRole("button", { name: "Load more" }));
      expect(await screen.findByText("Bob Builder")).toBeTruthy();
      expect(cursors).toEqual([null, "next-1"]);
      expect(screen.getAllByTestId("user-row")).toHaveLength(2);
      expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
    });

    it("shows no Load more button when the first page is the last", async () => {
      useList([ADA]);
      renderWithClient(<UsersTable />, makeNoRetryClient());
      await screen.findByText("Ada Lovelace");
      expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
    });
  });

  it("has the Invite user button", async () => {
    useList([ADA]);
    renderWithClient(<UsersTable />, makeNoRetryClient());
    expect(await screen.findByRole("button", { name: "Invite user" })).toBeTruthy();
  });
});

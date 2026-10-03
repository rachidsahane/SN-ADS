/**
 * `InviteUserDialog` : testé à travers `UsersTable`, qui porte le bouton « Invite user », ouvre la boîte de
 * dialogue et affiche l'avis de réussite (le composant de dialogue n'a pas d'interface propre imposée par la spec).
 * Champs : « Email », « Full name », « Role » (Marketer par défaut). Envoi : POST /api/v1/admin/users/invite.
 *
 * Écart avec la spec (3.D) : « empty submit shows the three field messages » ; le rôle ayant « Marketer » par défaut,
 * seuls l'e-mail et le nom peuvent être vides : deux messages sont attendus.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UsersTable } from "@/components/admin/users-table";
import { labels } from "@/lib/labels";

import {
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
const INVITE_URL = `${BASE}/api/v1/admin/users/invite`;

async function openDialog() {
  const user = userEvent.setup();
  renderWithClient(<UsersTable />, makeNoRetryClient());
  await user.click(await screen.findByRole("button", { name: "Invite user" }));
  const dialog = await screen.findByRole("dialog", { name: "Invite user" });
  return { user, dialog: within(dialog), dialogElement: dialog };
}

describe("InviteUserDialog (through UsersTable)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
    auth.signOut.mockResolvedValue({ error: null });
    server.use(
      http.get(`${BASE}/api/v1/me`, () => HttpResponse.json(adminMeFixture())),
      http.get(`${BASE}/api/v1/admin/users`, () => HttpResponse.json(adminUsersPage([]))),
    );
  });

  it("opens from the Invite user button as a modal dialog with Email, Full name and Role fields", async () => {
    const { dialog, dialogElement } = await openDialog();
    expect(dialogElement.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getByLabelText("Email")).toBeTruthy();
    expect(dialog.getByLabelText("Full name")).toBeTruthy();
    const role = dialog.getByLabelText("Role") as HTMLSelectElement;
    expect(role.value).toBe("marketer");
    expect(Array.from(role.options).map((option) => option.text)).toEqual(["Marketer", "Admin"]);
    expect(dialog.getByRole("button", { name: "Send invitation" })).toBeTruthy();
    expect(dialog.getByRole("button", { name: "Cancel" })).toBeTruthy();
  });

  it("is closed until the button is clicked", async () => {
    renderWithClient(<UsersTable />, makeNoRetryClient());
    await screen.findByRole("button", { name: "Invite user" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the field messages for an empty submit and sends no request", async () => {
    let calls = 0;
    server.use(
      http.post(INVITE_URL, () => {
        calls += 1;
        return HttpResponse.json(adminUserFixture(), { status: 201 });
      }),
    );
    const { user, dialog } = await openDialog();
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    expect(await dialog.findByText("Enter an email address.")).toBeTruthy();
    expect(dialog.getByText("Enter a full name.")).toBeTruthy();
    expect(calls).toBe(0);
  });

  it("links each field message to its field with aria-invalid and aria-describedby", async () => {
    const { user, dialog } = await openDialog();
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    await dialog.findByText("Enter an email address.");
    const email = dialog.getByLabelText("Email");
    expect(email.getAttribute("aria-invalid")).toBe("true");
    const describedBy = email.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy ?? "")?.textContent).toBe("Enter an email address.");
  });

  it("refuses an invalid e-mail without a request", async () => {
    let calls = 0;
    server.use(
      http.post(INVITE_URL, () => {
        calls += 1;
        return HttpResponse.json(adminUserFixture(), { status: 201 });
      }),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "not-an-email");
    await user.type(dialog.getByLabelText("Full name"), "Some Name");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    expect(await dialog.findByText("Enter a valid email address.")).toBeTruthy();
    expect(calls).toBe(0);
  });

  it("posts exactly {email (lower case), full_name, role}, closes, and shows the success notice", async () => {
    let received: unknown = null;
    server.use(
      http.post(INVITE_URL, async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(
          adminUserFixture({ email: "new.person@example.test", status: "invited" }),
          { status: 201 },
        );
      }),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "New.Person@Example.test");
    await user.type(dialog.getByLabelText("Full name"), "New Person");
    await user.selectOptions(dialog.getByLabelText("Role"), "admin");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(received).toEqual({
      email: "new.person@example.test",
      full_name: "New Person",
      role: "admin",
    });
    expect(screen.getByText("Invitation sent to new.person@example.test.")).toBeTruthy();
  });

  it("defaults the role to marketer in the request", async () => {
    let received: unknown = null;
    server.use(
      http.post(INVITE_URL, async ({ request }) => {
        received = await request.json();
        return HttpResponse.json(adminUserFixture({ status: "invited" }), { status: 201 });
      }),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "someone@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Some One");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect((received as { role: string }).role).toBe("marketer");
  });

  it("shows the 409 message next to the e-mail field, keeps the dialog open and keeps the values", async () => {
    server.use(
      http.post(INVITE_URL, () =>
        HttpResponse.json(
          apiErrorBody("EMAIL_ALREADY_REGISTERED", "A user with this email already exists."),
          { status: 409 },
        ),
      ),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "ada@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Ada Again");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));

    const message = await dialog.findByText("A user with this email already exists.");
    const email = dialog.getByLabelText("Email") as HTMLInputElement;
    expect(email.getAttribute("aria-describedby")).toBe(message.id);
    expect(message.getAttribute("role")).toBe("alert");
    expect(screen.getByRole("dialog", { name: "Invite user" })).toBeTruthy();
    expect(email.value).toBe("ada@example.test");
    expect((dialog.getByLabelText("Full name") as HTMLInputElement).value).toBe("Ada Again");
    expect(screen.queryByText(/Invitation sent to/)).toBeNull();
  });

  it("shows the service-unavailable text in the dialog on a 503", async () => {
    server.use(
      http.post(INVITE_URL, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", labels.errors.serviceUnavailable), {
          status: 503,
        }),
      ),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "ada2@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Ada Two");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    const alert = await dialog.findByRole("alert");
    expect(alert.textContent).toContain(labels.errors.serviceUnavailable);
    expect(screen.getByRole("dialog", { name: "Invite user" })).toBeTruthy();
  });

  it("never echoes a raw 422 detail", async () => {
    server.use(
      http.post(INVITE_URL, () =>
        HttpResponse.json(
          {
            error: {
              code: "VALIDATION_ERROR",
              message: "Some fields are invalid.",
              details: [{ field: "email", issue: "invalid_format", message: "RAW-DETAIL-TEXT" }],
              request_id: "rid",
            },
          },
          { status: 422 },
        ),
      ),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "ada3@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Ada Three");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    await dialog.findByRole("alert");
    expect(document.body.textContent).not.toContain("RAW-DETAIL-TEXT");
  });

  it("closes on Escape and on Cancel", async () => {
    const { user } = await openDialog();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await user.click(screen.getByRole("button", { name: "Invite user" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Invite user" }));
    await user.click(dialog.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("moves the focus into the dialog when it opens", async () => {
    const { dialogElement } = await openDialog();
    await waitFor(() => expect(dialogElement.contains(document.activeElement)).toBe(true));
  });

  it("disables the submit button and shows 'Sending…' while the request is pending", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post(INVITE_URL, async () => {
        await gate;
        return HttpResponse.json(adminUserFixture({ status: "invited" }), { status: 201 });
      }),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "slow@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Slow Person");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));

    const pending = await dialog.findByRole("button", { name: "Sending…" });
    expect((pending as HTMLButtonElement).disabled).toBe(true);
    release();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("reloads the user list after a successful invitation (the new row appears Invited)", async () => {
    let invited = false;
    server.use(
      http.get(`${BASE}/api/v1/admin/users`, () =>
        HttpResponse.json(
          adminUsersPage(
            invited
              ? [
                  adminUserFixture({
                    email: "fresh@example.test",
                    full_name: "Fresh",
                    status: "invited",
                  }),
                ]
              : [],
          ),
        ),
      ),
      http.post(INVITE_URL, () => {
        invited = true;
        return HttpResponse.json(
          adminUserFixture({ email: "fresh@example.test", full_name: "Fresh", status: "invited" }),
          { status: 201 },
        );
      }),
    );
    const { user, dialog } = await openDialog();
    await user.type(dialog.getByLabelText("Email"), "fresh@example.test");
    await user.type(dialog.getByLabelText("Full name"), "Fresh");
    await user.click(dialog.getByRole("button", { name: "Send invitation" }));
    const row = await screen.findByTestId("user-row");
    expect(within(row).getByTestId("user-status").textContent).toBe("Invited");
  });
});

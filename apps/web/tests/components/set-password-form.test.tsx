import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SetPasswordForm } from "@/components/auth/set-password-form";
import { labels } from "@/lib/labels";

import { authError } from "../helpers/fixtures";

const auth = vi.hoisted(() => ({ updateUser: vi.fn() }));
const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(""),
}));

/** Valeurs factices construites à l'exécution (aucun mot de passe réel dans le dépôt). */
const valueOf = (length: number, mark = "a") => mark.repeat(length);

async function submit(password: string, confirmation = password) {
  const user = userEvent.setup();
  if (password) {
    await user.type(screen.getByLabelText("Password"), password);
  }
  if (confirmation) {
    await user.type(screen.getByLabelText("Confirm password"), confirmation);
  }
  await user.click(screen.getByRole("button", { name: "Set password" }));
}

describe("SetPasswordForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.updateUser.mockResolvedValue({ data: { user: { id: "u" } }, error: null });
  });

  it("renders the two password fields and the Set password button", () => {
    render(<SetPasswordForm />);
    expect(screen.getByLabelText("Password")).toHaveProperty("type", "password");
    expect(screen.getByLabelText("Confirm password")).toHaveProperty("type", "password");
    expect(screen.getByLabelText("Password").getAttribute("autocomplete")).toBe("new-password");
    expect(screen.getByLabelText("Confirm password").getAttribute("autocomplete")).toBe(
      "new-password",
    );
    expect(screen.getByRole("button", { name: "Set password" })).toBeTruthy();
  });

  it("refuses 9 characters with the PRD message and does not call Supabase", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(9));
    expect(await screen.findByText("Password must be at least 10 characters.")).toBeTruthy();
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("refuses 73 characters", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(73));
    expect(await screen.findByText(labels.auth.setPassword.tooLong)).toBeTruthy();
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("flags a confirmation that does not match", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(12), valueOf(12, "b"));
    expect(await screen.findByText("Passwords do not match.")).toBeTruthy();
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("links the error to its field with aria-invalid and aria-describedby", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(9));
    await screen.findByText(labels.auth.setPassword.tooShort);
    const field = screen.getByLabelText("Password");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    expect(document.getElementById(field.getAttribute("aria-describedby") ?? "")?.textContent).toBe(
      labels.auth.setPassword.tooShort,
    );
  });

  it("calls updateUser with the new password then goes to /predict", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    await waitFor(() => expect(auth.updateUser).toHaveBeenCalledWith({ password: valueOf(12) }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict"));
  });

  it("accepts exactly 10 characters", async () => {
    render(<SetPasswordForm />);
    await submit(valueOf(10));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict"));
  });

  it("maps weak_password to the too-short message", async () => {
    auth.updateUser.mockResolvedValue({
      data: { user: null },
      error: authError({ status: 422, code: "weak_password" }),
    });
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    expect((await screen.findByRole("alert")).textContent).toBe(labels.auth.setPassword.tooShort);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("maps same_password to the choose-another message", async () => {
    auth.updateUser.mockResolvedValue({
      data: { user: null },
      error: authError({ status: 422, code: "same_password" }),
    });
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Choose a password you have not used before.",
    );
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("redirects to /login?reason=invalid_link when there is no session any more", async () => {
    auth.updateUser.mockResolvedValue({
      data: { user: null },
      error: authError({
        name: "AuthSessionMissingError",
        status: 400,
        message: "Auth session missing!",
      }),
    });
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login?reason=invalid_link"));
  });

  it.each([
    ["a retryable fetch error", authError({ name: "AuthRetryableFetchError", status: 0 })],
    ["a 500", authError({ status: 500 })],
  ])("shows the service-unavailable text on %s", async (_name, error) => {
    auth.updateUser.mockResolvedValue({ data: { user: null }, error });
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("shows the service-unavailable text when the call throws", async () => {
    auth.updateUser.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
  });

  it("disables the button and shows 'Saving…' while pending", async () => {
    auth.updateUser.mockReturnValue(new Promise(() => undefined));
    render(<SetPasswordForm />);
    await submit(valueOf(12));
    const pending = await screen.findByRole("button", { name: "Saving…" });
    expect(pending).toHaveProperty("disabled", true);
  });
});

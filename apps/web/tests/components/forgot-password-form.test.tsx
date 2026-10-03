import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { labels } from "@/lib/labels";

import { authError } from "../helpers/fixtures";

const auth = vi.hoisted(() => ({ resetPasswordForEmail: vi.fn() }));
const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(""),
}));

const EMAIL = "e2e-reset@example.test";

async function submit(email: string = EMAIL) {
  const user = userEvent.setup();
  if (email) {
    await user.type(screen.getByLabelText("Email"), email);
  }
  await user.click(screen.getByRole("button", { name: "Send reset link" }));
}

describe("ForgotPasswordForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    auth.resetPasswordForEmail.mockResolvedValue({ data: {}, error: null });
  });

  it("renders the e-mail field, the submit button, the intro and a Back to sign in link", () => {
    render(<ForgotPasswordForm />);
    expect(screen.getByLabelText("Email").getAttribute("autocomplete")).toBe("email");
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeTruthy();
    expect(screen.getByText(labels.auth.forgot.intro)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to sign in" }).getAttribute("href")).toBe(
      "/login",
    );
  });

  it("asks Supabase Auth to send a reset link to the typed e-mail", async () => {
    render(<ForgotPasswordForm />);
    await submit();
    await waitFor(() => expect(auth.resetPasswordForEmail).toHaveBeenCalledTimes(1));
    expect(auth.resetPasswordForEmail.mock.calls[0]?.[0]).toBe(EMAIL);
  });

  it("shows the neutral confirmation after a successful request", async () => {
    render(<ForgotPasswordForm />);
    await submit();
    expect(await screen.findByText(labels.auth.forgot.sent)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the very same neutral confirmation on a 429 (no account enumeration)", async () => {
    auth.resetPasswordForEmail.mockResolvedValue({
      data: null,
      error: authError({ status: 429, code: "over_email_send_rate_limit" }),
    });
    render(<ForgotPasswordForm />);
    await submit();
    expect(
      await screen.findByText(
        "If an account exists for this email, a link to set a new password has been sent.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps the Back to sign in link once the confirmation is shown", async () => {
    render(<ForgotPasswordForm />);
    await submit();
    await screen.findByText(labels.auth.forgot.sent);
    expect(screen.getByRole("link", { name: "Back to sign in" })).toBeTruthy();
  });

  it("asks for the e-mail when it is empty, without calling Supabase", async () => {
    render(<ForgotPasswordForm />);
    await submit("");
    expect(await screen.findByText(labels.auth.emailRequired)).toBeTruthy();
    expect(auth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it("asks for a valid e-mail, without calling Supabase", async () => {
    render(<ForgotPasswordForm />);
    await submit("nope");
    expect(await screen.findByText(labels.auth.emailInvalid)).toBeTruthy();
    expect(auth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it.each([
    ["a retryable fetch error", authError({ name: "AuthRetryableFetchError", status: 0 })],
    ["a 500", authError({ status: 500 })],
  ])("shows the service-unavailable text on %s, not the confirmation", async (_name, error) => {
    auth.resetPasswordForEmail.mockResolvedValue({ data: null, error });
    render(<ForgotPasswordForm />);
    await submit();
    expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
    expect(screen.queryByText(labels.auth.forgot.sent)).toBeNull();
  });

  it("shows the service-unavailable text when the call throws", async () => {
    auth.resetPasswordForEmail.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ForgotPasswordForm />);
    await submit();
    expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
  });

  it("disables the button and shows 'Sending…' while pending", async () => {
    auth.resetPasswordForEmail.mockReturnValue(new Promise(() => undefined));
    render(<ForgotPasswordForm />);
    await submit();
    const pending = await screen.findByRole("button", { name: "Sending…" });
    expect(pending).toHaveProperty("disabled", true);
  });
});

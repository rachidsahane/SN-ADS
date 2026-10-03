import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/auth/login-form";
import { labels } from "@/lib/labels";

import { authError } from "../helpers/fixtures";

const auth = vi.hoisted(() => ({ signInWithPassword: vi.fn() }));
const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }));
const nav = vi.hoisted(() => ({ search: "" }));

vi.mock("@/lib/supabase/browser", () => ({ getBrowserSupabase: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(nav.search),
}));

/** Valeur factice construite à l'exécution (aucun mot de passe réel dans le dépôt). */
const PASSPHRASE = ["not", "a", "real", "value"].join("-");
const EMAIL = "e2e-marketer-a@example.test";

async function fillAndSubmit(email = EMAIL, passphrase = PASSPHRASE) {
  const user = userEvent.setup();
  if (email) {
    await user.type(screen.getByLabelText("Email"), email);
  }
  if (passphrase) {
    await user.type(screen.getByLabelText("Password"), passphrase);
  }
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  return user;
}

describe("LoginForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    nav.search = "";
    auth.signInWithPassword.mockResolvedValue({
      data: { session: { access_token: "x" }, user: { id: "u" } },
      error: null,
    });
  });

  it("renders the Email and Password fields, the Sign in button and the Forgot password? link", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText("Email")).toHaveProperty("type", "email");
    expect(screen.getByLabelText("Password")).toHaveProperty("type", "password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Forgot password?" }).getAttribute("href")).toBe(
      "/forgot-password",
    );
  });

  it("declares the browser autocomplete hints (email, current-password)", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText("Email").getAttribute("autocomplete")).toBe("email");
    expect(screen.getByLabelText("Password").getAttribute("autocomplete")).toBe("current-password");
  });

  it("shows no alert on first render", () => {
    render(<LoginForm />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  describe("validation (Zod, before any network call)", () => {
    it("asks for both fields when the form is empty", async () => {
      render(<LoginForm />);
      await fillAndSubmit("", "");
      expect(await screen.findByText(labels.auth.emailRequired)).toBeTruthy();
      expect(screen.getByText(labels.auth.passwordRequired)).toBeTruthy();
      expect(auth.signInWithPassword).not.toHaveBeenCalled();
    });

    it("asks for a valid e-mail address", async () => {
      render(<LoginForm />);
      await fillAndSubmit("not-an-email");
      expect(await screen.findByText(labels.auth.emailInvalid)).toBeTruthy();
      expect(auth.signInWithPassword).not.toHaveBeenCalled();
    });

    it("links each error to its field with aria-invalid and aria-describedby", async () => {
      render(<LoginForm />);
      await fillAndSubmit("", "");
      await screen.findByText(labels.auth.emailRequired);
      const email = screen.getByLabelText("Email");
      expect(email.getAttribute("aria-invalid")).toBe("true");
      const describedBy = email.getAttribute("aria-describedby");
      expect(describedBy).toBeTruthy();
      expect(document.getElementById(describedBy ?? "")?.textContent).toBe(
        labels.auth.emailRequired,
      );
      const password = screen.getByLabelText("Password");
      expect(
        document.getElementById(password.getAttribute("aria-describedby") ?? "")?.textContent,
      ).toBe(labels.auth.passwordRequired);
    });
  });

  describe("signing in", () => {
    it("sends the e-mail and password to Supabase Auth", async () => {
      render(<LoginForm />);
      await fillAndSubmit();
      await waitFor(() =>
        expect(auth.signInWithPassword).toHaveBeenCalledWith({
          email: EMAIL,
          password: PASSPHRASE,
        }),
      );
    });

    it("goes to /predict after a successful sign-in", async () => {
      render(<LoginForm />);
      await fillAndSubmit();
      await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict"));
    });

    it("goes to the safe ?next= path after a successful sign-in", async () => {
      nav.search = "next=%2Fhistory%2Fabc%3Fx%3D1";
      render(<LoginForm />);
      await fillAndSubmit();
      await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/history/abc?x=1"));
    });

    it.each(["//evil.com", "https://evil.com", "/\\evil.com"])(
      "ignores the unsafe ?next=%s and goes to /predict",
      async (next) => {
        nav.search = `next=${encodeURIComponent(next)}`;
        render(<LoginForm />);
        await fillAndSubmit();
        await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict"));
      },
    );

    it("disables the button and shows 'Signing in…' while the request is pending", async () => {
      auth.signInWithPassword.mockReturnValue(new Promise(() => undefined));
      render(<LoginForm />);
      await fillAndSubmit();
      const pending = await screen.findByRole("button", { name: "Signing in…" });
      expect(pending).toHaveProperty("disabled", true);
    });
  });

  describe("failures", () => {
    it("shows the generic message for invalid credentials and does not navigate", async () => {
      auth.signInWithPassword.mockResolvedValue({
        data: { session: null, user: null },
        error: authError({ status: 400, code: "invalid_credentials" }),
      });
      render(<LoginForm />);
      await fillAndSubmit();
      const alert = await screen.findByRole("alert");
      expect(alert.textContent).toBe("Invalid email or password.");
      expect(router.replace).not.toHaveBeenCalled();
    });

    it("gives the very same message for an unknown e-mail (same error code, no enumeration)", async () => {
      const failure = {
        data: { session: null, user: null },
        error: authError({ status: 400, code: "invalid_credentials" }),
      };
      auth.signInWithPassword.mockResolvedValue(failure);
      const first = render(<LoginForm />);
      await fillAndSubmit(EMAIL);
      const known = (await screen.findByRole("alert")).textContent;
      first.unmount();

      render(<LoginForm />);
      await fillAndSubmit("nobody-here@example.test");
      const unknown = (await screen.findByRole("alert")).textContent;
      expect(unknown).toBe(known);
    });

    it("never reveals the server's own wording for another 4xx", async () => {
      auth.signInWithPassword.mockResolvedValue({
        data: { session: null, user: null },
        error: authError({
          status: 400,
          code: "email_not_confirmed",
          message: "Email not confirmed",
        }),
      });
      render(<LoginForm />);
      await fillAndSubmit();
      expect((await screen.findByRole("alert")).textContent).toBe(
        labels.auth.signIn.invalidCredentials,
      );
    });

    it.each([
      ["over_request_rate_limit", 429],
      ["over_email_send_rate_limit", 429],
    ])("shows the too-many-requests message for %s", async (code, status) => {
      auth.signInWithPassword.mockResolvedValue({
        data: { session: null, user: null },
        error: authError({ status, code }),
      });
      render(<LoginForm />);
      await fillAndSubmit();
      expect((await screen.findByRole("alert")).textContent).toBe(
        "Too many requests. Please wait a moment.",
      );
    });

    it.each([
      [
        "a retryable fetch error",
        authError({ name: "AuthRetryableFetchError", status: 0, message: "fetch failed" }),
      ],
      ["a 502 from the gateway", authError({ status: 502, message: "Bad Gateway" })],
      ["a 500", authError({ status: 500, code: "unexpected_failure" })],
    ])("shows the service-unavailable text for %s", async (_name, error) => {
      auth.signInWithPassword.mockResolvedValue({ data: { session: null, user: null }, error });
      render(<LoginForm />);
      await fillAndSubmit();
      expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
      expect(router.replace).not.toHaveBeenCalled();
    });

    it("shows the service-unavailable text when the call throws (network down)", async () => {
      auth.signInWithPassword.mockRejectedValue(new TypeError("Failed to fetch"));
      render(<LoginForm />);
      await fillAndSubmit();
      expect((await screen.findByRole("alert")).textContent).toBe(labels.errors.serviceUnavailable);
    });

    it("re-enables the button after a failure so the user can retry", async () => {
      auth.signInWithPassword.mockResolvedValue({
        data: { session: null, user: null },
        error: authError({ status: 400, code: "invalid_credentials" }),
      });
      render(<LoginForm />);
      await fillAndSubmit();
      await screen.findByRole("alert");
      expect(screen.getByRole("button", { name: "Sign in" })).toHaveProperty("disabled", false);
    });

    it("clears the previous error on a new attempt that succeeds", async () => {
      auth.signInWithPassword.mockResolvedValueOnce({
        data: { session: null, user: null },
        error: authError({ status: 400, code: "invalid_credentials" }),
      });
      render(<LoginForm />);
      const user = await fillAndSubmit();
      await screen.findByRole("alert");
      await user.click(screen.getByRole("button", { name: "Sign in" }));
      await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/predict"));
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });

  describe("?reason=", () => {
    it("shows the invalid-link message for ?reason=invalid_link", () => {
      nav.search = "reason=invalid_link";
      render(<LoginForm />);
      expect(screen.getByRole("alert").textContent).toBe(
        "This link is invalid or has expired. Ask an administrator for a new invitation.",
      );
    });

    it("ignores unknown reasons", () => {
      nav.search = "reason=whatever";
      render(<LoginForm />);
      expect(screen.queryByRole("alert")).toBeNull();
    });
  });
});

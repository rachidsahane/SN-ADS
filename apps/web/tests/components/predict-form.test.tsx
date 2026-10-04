import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PredictView } from "@/components/predict/predict-view";

import { apiErrorBody, predictionFixture } from "../helpers/fixtures";
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

const BASE = "http://localhost:3000/api/v1";
const MODEL = { id: "22222222-2222-4222-8222-222222222222", version: 3 };
const OPTIONS = {
  currency: "USD",
  enums: {},
  limits: {},
  training_ranges: {},
  features_used: ["ad_spend"],
  optional_categories: {},
  model_version: MODEL,
};
const DEFAULTS = {
  pages_per_visit: 5.4,
  time_on_site: 7.8,
  social_shares: 50,
  email_opens: 9,
  email_clicks: 5,
  basis: "channel_and_type",
};
const INPUT = {
  campaign_channel: "Email",
  campaign_type: "Conversion",
  ad_spend: 5000,
  age: 38,
  gender: "Female",
  income: 65000,
  previous_purchases: 3,
  loyalty_points: 2200,
  ...Object.fromEntries(Object.entries(DEFAULTS).filter(([key]) => key !== "basis")),
};
const WAIT = { timeout: 4000 };

type Body = Record<string, unknown>;

function mockApi(options: Record<string, unknown> = OPTIONS) {
  const bodies: Body[] = [];
  server.use(
    http.get(`${BASE}/reference/options`, () => HttpResponse.json(options)),
    http.get(`${BASE}/reference/engagement-defaults`, ({ request }) => {
      const channel = new URL(request.url).searchParams.get("campaign_channel");
      return HttpResponse.json(
        channel === "PPC" ? { ...DEFAULTS, pages_per_visit: 6.5 } : DEFAULTS,
      );
    }),
    http.post(`${BASE}/predictions/simulate`, async ({ request }) => {
      bodies.push((await request.json()) as Body);
      return HttpResponse.json(predictionFixture({ input: INPUT }));
    }),
  );
  return bodies;
}

beforeEach(() => {
  vi.resetAllMocks();
  auth.getSession.mockResolvedValue({ data: { session: null }, error: null });
});

describe("PredictView (live results, no Predict button)", () => {
  it("shows the page header, a skeleton while loading, then the form in three blocks", async () => {
    mockApi();
    const { container } = renderWithClient(<PredictView />, makeNoRetryClient());
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Predict" })).toBeTruthy();
    expect(await screen.findByText("Campaign plan")).toBeTruthy();
    expect(screen.getByText("Target audience profile")).toBeTruthy();
    expect(screen.getByText("Expected engagement")).toBeTruthy();
    expect(screen.getByText("Known before launch")).toBeTruthy();
    expect(screen.getByText("Results update as you type.", { exact: false })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Predict" })).toBeNull();
  });

  it("shows a banner, disables the form and offers no results when no model is active", async () => {
    mockApi({ ...OPTIONS, model_version: null });
    renderWithClient(<PredictView />, makeNoRetryClient());
    expect((await screen.findByRole("status")).textContent).toContain("No active model yet");
    expect(screen.getByLabelText("Age").matches(":disabled")).toBe(true); // disabled by its fieldset
    expect(
      (screen.getByRole("button", { name: "Save prediction" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.queryByTestId("figure-card")).toBeNull();
    expect(screen.queryByTestId("model-tag")).toBeNull();
  });

  it("pre-fills the engagement then calculates once by itself, and shows the model tag", async () => {
    const bodies = mockApi();
    renderWithClient(<PredictView />, makeNoRetryClient());
    const pages = (await screen.findByLabelText("Pages per visit")) as HTMLInputElement;
    await waitFor(() => expect(pages.value).toBe("5.4"));
    expect(await screen.findAllByTestId("figure-card", {}, WAIT)).toHaveLength(3);
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({
      campaign_channel: "Email",
      campaign_type: "Conversion",
      ad_spend: 5000,
      age: 38,
      income: 65000,
      email_clicks: 5,
    });
    expect(bodies[0]).not.toHaveProperty("advertising_platform");
    expect(screen.getByTestId("model-tag").textContent).toBe("Model v3");
    expect(
      screen.getByText("Prefilled with the observed average for Email · Conversion."),
    ).toBeTruthy();
  });

  it("recalculates 400 ms after the last keystroke, with one request for the whole edit", async () => {
    const bodies = mockApi();
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    const age = screen.getByLabelText("Age");
    await userEvent.clear(age);
    await userEvent.type(age, "41");
    expect(await screen.findByText("Recalculating…", {}, WAIT)).toBeTruthy();
    await waitFor(() => expect(bodies).toHaveLength(2), WAIT);
    expect(bodies[1]).toMatchObject({ age: 41 });
    await waitFor(() => expect(screen.queryByText("Recalculating…")).toBeNull(), WAIT);
  });

  it("accepts thousands separators and reports bad values without calling the API", async () => {
    const bodies = mockApi();
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    const income = screen.getByLabelText("Income (USD / year)");
    await userEvent.clear(income);
    await userEvent.type(income, "70,000");
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ income: 70000 }), WAIT);
    const count = bodies.length;

    const age = screen.getByLabelText("Age");
    await userEvent.clear(age);
    expect(await screen.findByText("Required.")).toBeTruthy();
    await userEvent.type(age, "17");
    expect(await screen.findByText("Age must be between 18 and 100.")).toBeTruthy();
    expect(age.getAttribute("aria-invalid")).toBe("true");
    await userEvent.clear(age);
    await userEvent.type(age, "abc");
    expect(await screen.findByText("Enter a number.")).toBeTruthy();
    await userEvent.clear(age);
    await userEvent.type(age, "20.5");
    expect(await screen.findByText("Must be a whole number.")).toBeTruthy();
    const spend = screen.getByLabelText("Ad spend (USD)");
    await userEvent.clear(spend);
    await userEvent.type(spend, "0");
    expect(await screen.findByText("Ad spend must be greater than 0.")).toBeTruthy();

    // Results are hidden while the form is invalid, and nothing was sent.
    expect(
      screen.getByText("Fix the highlighted fields to see the predicted results."),
    ).toBeTruthy();
    expect(screen.queryByTestId("figure-card")).toBeNull();
    expect(
      (screen.getByRole("button", { name: "Save prediction" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(bodies).toHaveLength(count);
  });

  it("warns, without blocking, about a value outside what the model has seen", async () => {
    const bodies = mockApi({
      ...OPTIONS,
      training_ranges: { ad_spend: { min: 100, max: 9000 } },
    });
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    expect(screen.queryByTestId("field-warning")).toBeNull();
    const spend = screen.getByLabelText("Ad spend (USD)");
    await userEvent.clear(spend);
    await userEvent.type(spend, "12000");
    expect((await screen.findByTestId("field-warning")).textContent).toBe(
      "Outside the values the model has seen. Treat this prediction with caution.",
    );
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ ad_spend: 12000 }), WAIT);
  });

  it("changing the channel reloads the average engagement, editing an engagement field does not", async () => {
    const bodies = mockApi();
    renderWithClient(<PredictView />, makeNoRetryClient());
    const pages = (await screen.findByLabelText("Pages per visit")) as HTMLInputElement;
    await waitFor(() => expect(pages.value).toBe("5.4"));
    await screen.findAllByTestId("figure-card", {}, WAIT);

    await userEvent.clear(pages);
    await userEvent.type(pages, "9");
    expect(pages.value).toBe("9");
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ pages_per_visit: 9 }), WAIT);

    await userEvent.selectOptions(screen.getByLabelText("Channel"), "PPC");
    await waitFor(() => expect(pages.value).toBe("6.5"), WAIT);
    expect(
      screen.getByText("Prefilled with the observed average for PPC · Conversion."),
    ).toBeTruthy();

    await userEvent.clear(pages);
    await userEvent.type(pages, "2");
    await userEvent.click(screen.getByRole("button", { name: "Reset to averages" }));
    await waitFor(() => expect(pages.value).toBe("6.5"), WAIT);
  });

  it("applies a recommendation: the field changes and the result is recalculated", async () => {
    const bodies = mockApi();
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ campaign_channel: "PPC" }), WAIT);
    expect((screen.getByLabelText("Channel") as HTMLSelectElement).value).toBe("PPC");
  });

  it("shows the message of the API when the simulation fails, and keeps Save off", async () => {
    mockApi();
    server.use(
      http.post(`${BASE}/predictions/simulate`, () =>
        HttpResponse.json(apiErrorBody("SERVICE_UNAVAILABLE", "Back-end is down."), {
          status: 503,
        }),
      ),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    expect((await screen.findByRole("alert", {}, WAIT)).textContent).toBe("Back-end is down.");
    expect(
      (screen.getByRole("button", { name: "Save prediction" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("saves with an optional name (default 'Channel · Type'), then confirms with a toast", async () => {
    mockApi();
    const saved: Body[] = [];
    server.use(
      http.post(`${BASE}/predictions`, async ({ request }) => {
        saved.push((await request.json()) as Body);
        return HttpResponse.json(predictionFixture({ id: "x", input: INPUT }), { status: 201 });
      }),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    await userEvent.click(screen.getByRole("button", { name: "Save prediction" }));
    const dialog = within(screen.getByRole("dialog", { name: "Save prediction" }));
    const name = dialog.getByLabelText("Name (optional)") as HTMLInputElement;
    expect(name.placeholder).toBe("e.g. Black Friday email");
    expect(dialog.getByText("0 / 100")).toBeTruthy();
    await userEvent.type(name, "Hello");
    expect(dialog.getByText("5 / 100")).toBeTruthy();
    await userEvent.clear(name);
    await userEvent.click(dialog.getByRole("button", { name: "Save prediction" }));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0]).toEqual({ name: "Email · Conversion", input: INPUT });
    expect((await screen.findByTestId("toast")).textContent).toBe("Prediction saved to History.");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes the save dialog with Cancel and sends nothing", async () => {
    mockApi();
    const post = vi.fn();
    server.use(
      http.post(`${BASE}/predictions`, () => {
        post();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithClient(<PredictView />, makeNoRetryClient());
    await screen.findAllByTestId("figure-card", {}, WAIT);
    await userEvent.click(screen.getByRole("button", { name: "Save prediction" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });
});

describe("PredictView with a saved prediction", () => {
  const SAVED_ID = "33333333-3333-4333-8333-333333333333";

  function mockSaved() {
    const bodies = mockApi();
    server.use(
      http.get(`${BASE}/predictions/${SAVED_ID}`, () =>
        HttpResponse.json(
          predictionFixture({
            id: SAVED_ID,
            label: "Spring push",
            created_at: "2026-10-04T10:30:00Z",
            input: { ...INPUT, age: 52, campaign_channel: "SEO" },
            model_version: { id: MODEL.id, version: 2 },
          }),
        ),
      ),
    );
    return bodies;
  }

  it("shows the frozen result read-only, with the viewing bar and the saved values, and no request", async () => {
    const bodies = mockSaved();
    renderWithClient(<PredictView savedId={SAVED_ID} />, makeNoRetryClient());
    const bar = await screen.findByTestId("viewing-bar", {}, WAIT);
    expect(bar.textContent).toContain("Viewing saved prediction");
    expect(bar.textContent).toContain("“Spring push”");
    expect(bar.textContent).toContain("with model v2");
    expect(within(bar).getByRole("link", { name: "Back to history" }).getAttribute("href")).toBe(
      "/history",
    );
    expect((screen.getByLabelText("Age") as HTMLInputElement).value).toBe("52");
    expect((screen.getByLabelText("Channel") as HTMLSelectElement).value).toBe("SEO");
    expect(await screen.findAllByTestId("figure-card")).toHaveLength(3);
    expect(screen.getByTestId("model-tag").textContent).toBe("Model v2");
    expect(
      (screen.getByRole("button", { name: "Save prediction" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(bodies).toHaveLength(0);
  });

  it("editing a field starts a new simulation and leaves the viewing mode", async () => {
    const bodies = mockSaved();
    renderWithClient(<PredictView savedId={SAVED_ID} />, makeNoRetryClient());
    await screen.findByTestId("viewing-bar", {}, WAIT);
    const age = screen.getByLabelText("Age");
    await userEvent.clear(age);
    await userEvent.type(age, "53");
    await waitFor(() => expect(bodies).toHaveLength(1), WAIT);
    expect(bodies[0]).toMatchObject({ age: 53, campaign_channel: "SEO" });
    await waitFor(() => expect(screen.queryByTestId("viewing-bar")).toBeNull(), WAIT);
    await waitFor(
      () =>
        expect(
          (screen.getByRole("button", { name: "Save prediction" }) as HTMLButtonElement).disabled,
        ).toBe(false),
      WAIT,
    );
  });

  it("shows the message of the API and a way back when the prediction is not yours", async () => {
    mockApi();
    server.use(
      http.get(`${BASE}/predictions/${SAVED_ID}`, () =>
        HttpResponse.json(apiErrorBody("NOT_FOUND", "Prediction not found."), { status: 404 }),
      ),
    );
    renderWithClient(<PredictView savedId={SAVED_ID} />, makeNoRetryClient());
    expect((await screen.findByRole("alert")).textContent).toBe("Prediction not found.");
    expect(screen.getByRole("link", { name: "Back to history" }).getAttribute("href")).toBe(
      "/history",
    );
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { ApiStatus } from "@/components/feedback/api-status";

import { server } from "../msw/server";

const HEALTH_URL = "http://localhost:3000/api/health";

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApiStatus />
    </QueryClientProvider>,
  );
}

describe("ApiStatus", () => {
  it("shows a checking state before the API answers", () => {
    server.use(http.get(HEALTH_URL, () => new Promise(() => undefined)));
    renderStatus();
    const status = screen.getByTestId("api-status");
    expect(status.getAttribute("data-state")).toBe("checking");
    expect(status.textContent).toBe("API: checking…");
  });

  it("shows 'API: healthy' when the API answers ok", async () => {
    server.use(http.get(HEALTH_URL, () => HttpResponse.json({ status: "ok", release: "abc123" })));
    renderStatus();
    expect(
      (await screen.findByText("API: healthy")).closest("[data-state]")?.getAttribute("data-state"),
    ).toBe("healthy");
  });

  it("shows 'API: unreachable' when the network fails", async () => {
    server.use(http.get(HEALTH_URL, () => HttpResponse.error()));
    renderStatus();
    await screen.findByText("API: unreachable");
    expect(screen.getByTestId("api-status").getAttribute("data-state")).toBe("unreachable");
  });

  it("shows 'API: unreachable' when the proxy answers 500", async () => {
    server.use(
      http.get(HEALTH_URL, () => new HttpResponse("Internal Server Error", { status: 500 })),
    );
    renderStatus();
    await screen.findByText("API: unreachable");
  });

  it("shows 'API: unreachable' when the body is not the expected health payload", async () => {
    server.use(http.get(HEALTH_URL, () => HttpResponse.json({ status: "degraded", release: "x" })));
    renderStatus();
    await screen.findByText("API: unreachable");
  });
});

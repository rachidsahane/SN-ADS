import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DatabaseStatus } from "@/components/feedback/database-status";

import { server } from "../msw/server";

const READY_URL = "http://localhost:3000/api/ready";
const SCHEMA = "20261003120000";

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <DatabaseStatus />
    </QueryClientProvider>,
  );
  return { client, ...view };
}

describe("DatabaseStatus", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a checking state before the API answers", () => {
    server.use(http.get(READY_URL, () => new Promise(() => undefined)));
    renderStatus();
    const status = screen.getByTestId("database-status");
    expect(status.getAttribute("data-state")).toBe("checking");
    expect(status.textContent).toBe("Database: checking…");
  });

  it("shows the schema number when the database is connected", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json({
          status: "ready",
          checks: { database: "ok" },
          schema_version: SCHEMA,
          release: "x",
        }),
      ),
    );
    renderStatus();
    await screen.findByText(`Database: connected (schema ${SCHEMA})`);
    const status = screen.getByTestId("database-status");
    expect(status.textContent).toBe(`Database: connected (schema ${SCHEMA})`);
    expect(status.getAttribute("data-state")).toBe("connected");
  });

  it("shows 'Database: unreachable' when the network fails", async () => {
    server.use(http.get(READY_URL, () => HttpResponse.error()));
    renderStatus();
    await screen.findByText("Database: unreachable");
    expect(screen.getByTestId("database-status").getAttribute("data-state")).toBe("unreachable");
  });

  it("shows 'Database: unreachable' when readiness answers 503 not_ready", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json(
          { status: "not_ready", checks: { database: "error" }, release: "x" },
          { status: 503 },
        ),
      ),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
    expect(screen.getByTestId("database-status").getAttribute("data-state")).toBe("unreachable");
  });

  it("shows 'Database: unreachable' when the proxy answers a non-JSON 500", async () => {
    server.use(
      http.get(READY_URL, () => new HttpResponse("Internal Server Error", { status: 500 })),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
    expect(screen.getByTestId("database-status").getAttribute("data-state")).toBe("unreachable");
  });

  it("shows 'Database: unreachable' when a 200 body says not_ready", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json({
          status: "not_ready",
          checks: { database: "error" },
          schema_version: SCHEMA,
          release: "x",
        }),
      ),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
  });

  it("shows 'Database: unreachable' when the database check is not ok", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json({
          status: "ready",
          checks: { database: "error" },
          schema_version: SCHEMA,
          release: "x",
        }),
      ),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
  });

  it("shows 'Database: unreachable' when the schema version is missing", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json({ status: "ready", checks: { database: "ok" }, release: "x" }),
      ),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
  });

  it("shows 'Database: unreachable' when the schema version is empty", async () => {
    server.use(
      http.get(READY_URL, () =>
        HttpResponse.json({
          status: "ready",
          checks: { database: "ok" },
          schema_version: "",
          release: "x",
        }),
      ),
    );
    renderStatus();
    await screen.findByText("Database: unreachable");
  });

  it("moves from connected to unreachable on the next refresh when readiness starts failing", async () => {
    let failing = false;
    server.use(
      http.get(READY_URL, () =>
        failing
          ? HttpResponse.json(
              { status: "not_ready", checks: { database: "error" }, release: "x" },
              { status: 503 },
            )
          : HttpResponse.json({
              status: "ready",
              checks: { database: "ok" },
              schema_version: SCHEMA,
              release: "x",
            }),
      ),
    );
    const { client } = renderStatus();
    await screen.findByText(`Database: connected (schema ${SCHEMA})`);

    failing = true;
    await act(async () => {
      await client.invalidateQueries();
    });

    await waitFor(() =>
      expect(screen.getByTestId("database-status").getAttribute("data-state")).toBe("unreachable"),
    );
    expect(screen.getByTestId("database-status").textContent).toBe("Database: unreachable");
  });

  it.each([
    ["an empty object", {}],
    ["a JSON null", null],
    ["a body without checks", { status: "ready", schema_version: SCHEMA, release: "x" }],
    [
      "a numeric schema version",
      { status: "ready", checks: { database: "ok" }, schema_version: 20261003120000, release: "x" },
    ],
  ])("shows 'Database: unreachable' when a 200 answer carries %s", async (_name, body) => {
    server.use(http.get(READY_URL, () => HttpResponse.json(body)));
    renderStatus();
    await screen.findByText("Database: unreachable");
    expect(screen.getByTestId("database-status").getAttribute("data-state")).toBe("unreachable");
  });

  it("colours each state: neutral while checking, green when connected, red when unreachable", async () => {
    let answer: "ok" | "down" = "ok";
    server.use(
      http.get(READY_URL, () =>
        answer === "ok"
          ? HttpResponse.json({
              status: "ready",
              checks: { database: "ok" },
              schema_version: SCHEMA,
              release: "x",
            })
          : HttpResponse.error(),
      ),
    );
    const { client } = renderStatus();
    const status = screen.getByTestId("database-status");
    expect(status.className).toContain("text-neutral-700");
    await screen.findByText(`Database: connected (schema ${SCHEMA})`);
    expect(status.className).toContain("text-success");
    expect(status.className).not.toContain("text-danger");

    answer = "down";
    await act(async () => {
      await client.invalidateQueries();
    });
    await screen.findByText("Database: unreachable");
    expect(status.className).toContain("text-danger");
    expect(status.className).not.toContain("text-success");
  });

  it("polls the readiness route on its own every 5 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      http.get(READY_URL, () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({
              status: "ready",
              checks: { database: "ok" },
              schema_version: SCHEMA,
              release: "x",
            })
          : HttpResponse.json(
              { status: "not_ready", checks: { database: "error" }, release: "x" },
              { status: 503 },
            );
      }),
    );
    renderStatus();
    await screen.findByText(`Database: connected (schema ${SCHEMA})`);
    expect(calls).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_100);
    });

    await screen.findByText("Database: unreachable");
    expect(calls).toBe(2);
  });
});

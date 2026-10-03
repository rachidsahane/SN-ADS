import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

/** Cache de test : mêmes défauts que l'application, sauf les nouvelles tentatives (tests déterministes). */
export function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });
}

export function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

export function renderWithClient(ui: ReactElement, client: QueryClient = makeQueryClient()) {
  return { client, ...render(ui, { wrapper: wrapperFor(client) }) };
}

/**
 * Cache de test sans nouvelle tentative : une erreur d'API s'affiche tout de suite
 * (les écrans d'administration n'imposent pas `retry: false` eux-mêmes).
 */
export function makeNoRetryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: false }, mutations: { retry: false } },
  });
}

import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost:3000" } },
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    env: {
      NEXT_PUBLIC_APP_ENV: "local",
      NEXT_PUBLIC_APP_RELEASE: "test",
    },
    restoreMocks: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      // Exclusions justifiées dans docs/decisions.md : types générés, composants shadcn/ui copiés tels quels.
      exclude: ["src/lib/api/types.gen.ts", "src/components/ui/**"],
      thresholds: {
        "src/lib/**": { lines: 85, branches: 80 },
        "src/hooks/**": { lines: 85, branches: 80 },
        "src/components/**": { lines: 70, branches: 60 },
      },
    },
  },
});

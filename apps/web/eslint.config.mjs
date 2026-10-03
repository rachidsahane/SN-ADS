import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: dirname(fileURLToPath(import.meta.url)) });

// Fichiers autorisés à lire process.env (CONVENTIONS.md section 6 : modules de configuration).
const ENV_READERS = [
  "src/lib/env.ts",
  "next.config.ts",
  "playwright.config.ts",
  "vitest.config.ts",
  "instrumentation.ts",
  "instrumentation-client.ts",
  "sentry.server.config.ts",
  "sentry.edge.config.ts",
  "e2e/**/*.ts",
  "tests/**/*.{ts,tsx}",
];

const eslintConfig = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "coverage/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
      "src/lib/api/types.gen.ts",
    ],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      "no-console": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "react-hooks/exhaustive-deps": "error",
      "no-restricted-globals": [
        "error",
        {
          name: "localStorage",
          message: "Use sessionStorage for drafts; the session is managed by Supabase.",
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[object.name='process'][property.name='env']",
          message: "Read configuration only in src/lib/env.ts (CONVENTIONS.md).",
        },
      ],
    },
  },
  {
    files: ENV_READERS,
    rules: { "no-restricted-syntax": "off" },
  },
  {
    files: ["src/lib/observability.ts"],
    rules: { "no-console": ["error", { allow: ["error"] }] },
  },
];

export default eslintConfig;

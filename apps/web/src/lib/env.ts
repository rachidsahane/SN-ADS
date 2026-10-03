import { z } from "zod";

/** Une variable vide (`VAR=`) est traitée comme absente. */
const emptyToUndefined = (value: unknown): unknown =>
  typeof value === "string" && value.trim() === "" ? undefined : value;

const optionalString = z.preprocess(emptyToUndefined, z.string().min(1).optional());
const optionalUrl = z.preprocess(emptyToUndefined, z.string().url().optional());

/**
 * Variables NEXT_PUBLIC_* (ENV_SETUP.md section 3). Elles sont incluses dans le code du navigateur :
 * jamais de secret ici. Les variables Supabase et Sentry deviennent obligatoires aux phases 2 et 16.
 */
const publicSchema = z.object({
  NEXT_PUBLIC_APP_ENV: z.enum(["local", "staging", "production"]),
  NEXT_PUBLIC_APP_RELEASE: z.string().trim().min(1),
  NEXT_PUBLIC_SUPABASE_URL: optionalUrl,
  NEXT_PUBLIC_SUPABASE_ANON_KEY: optionalString,
  NEXT_PUBLIC_SENTRY_DSN: optionalUrl,
});

export type PublicEnv = z.infer<typeof publicSchema>;

export class EnvError extends Error {
  constructor(public readonly variables: string[]) {
    super(`Invalid environment variables: ${variables.join(", ")}`);
    this.name = "EnvError";
  }
}

/** Valide un objet de variables. Le message liste les noms et les types d'erreur, jamais les valeurs. */
export function parsePublicEnv(source: Record<string, string | undefined>): PublicEnv {
  const result = publicSchema.safeParse(source);
  if (result.success) {
    return result.data;
  }
  const variables = [
    ...new Set(result.error.issues.map((issue) => `${issue.path.join(".")} (${issue.code})`)),
  ];
  throw new EnvError(variables);
}

// Chaque variable est citée littéralement : Next.js ne remplace process.env.NEXT_PUBLIC_X
// dans le code du navigateur que pour cette forme exacte (pas de process.env[nom]).
export const env: PublicEnv = parsePublicEnv({
  NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV,
  NEXT_PUBLIC_APP_RELEASE: process.env.NEXT_PUBLIC_APP_RELEASE,
  NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
  NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
});

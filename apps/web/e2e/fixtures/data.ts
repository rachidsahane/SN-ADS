// Comptes et adresses de test lus dans l'environnement du conteneur `e2e` (docker-compose.yml).
// Les comptes sont créés avant Playwright par `make test-users` (conteneur `cli`) : le conteneur
// `e2e` ne porte JAMAIS la clé de service Supabase (SECURITY_NOTES 5, décision C2 de la phase 2).
// Les mots de passe viennent du `.env` local (générés par `make env-local`), jamais d'un fichier versionné.

export type Account = { email: string; password: string };

export type Accounts = {
  marketerA: Account;
  marketerB: Account;
  admin: Account;
  admin2: Account;
  reset: Account;
  inviteeEmail: string;
  mailpitUrl: string;
};

const ACCOUNT_VARIABLES = {
  marketerA: "E2E_MARKETER_A",
  marketerB: "E2E_MARKETER_B",
  admin: "E2E_ADMIN",
  admin2: "E2E_ADMIN2",
  reset: "E2E_RESET",
} as const;

let cached: Accounts | undefined;

/** Lit les variables de test ; échoue en listant les NOMS manquants (jamais les valeurs). */
export function getAccounts(): Accounts {
  if (cached) return cached;

  const missing: string[] = [];
  const read = (name: string): string => {
    const value = process.env[name];
    if (!value) {
      missing.push(name);
      return "";
    }
    return value;
  };

  const accounts: Accounts = {
    marketerA: {
      email: read(`${ACCOUNT_VARIABLES.marketerA}_EMAIL`),
      password: read(`${ACCOUNT_VARIABLES.marketerA}_PASSWORD`),
    },
    marketerB: {
      email: read(`${ACCOUNT_VARIABLES.marketerB}_EMAIL`),
      password: read(`${ACCOUNT_VARIABLES.marketerB}_PASSWORD`),
    },
    admin: {
      email: read(`${ACCOUNT_VARIABLES.admin}_EMAIL`),
      password: read(`${ACCOUNT_VARIABLES.admin}_PASSWORD`),
    },
    admin2: {
      email: read(`${ACCOUNT_VARIABLES.admin2}_EMAIL`),
      password: read(`${ACCOUNT_VARIABLES.admin2}_PASSWORD`),
    },
    reset: {
      email: read(`${ACCOUNT_VARIABLES.reset}_EMAIL`),
      password: read(`${ACCOUNT_VARIABLES.reset}_PASSWORD`),
    },
    inviteeEmail: read("E2E_INVITEE_EMAIL"),
    mailpitUrl: read("E2E_MAILPIT_URL"),
  };

  if (missing.length > 0) {
    throw new Error(
      `Missing E2E environment variables (run "make env-local"): ${missing.join(", ")}`,
    );
  }
  cached = accounts;
  return accounts;
}

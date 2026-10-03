import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { env } from "@/lib/env";
import { serialLock } from "@/lib/supabase/lock";
import { AUTH_COOKIE_OPTIONS } from "@/lib/supabase/shared";

let client: SupabaseClient | undefined;

/**
 * Client Supabase du navigateur (singleton). Il parle toujours à sa propre origine : `/auth/v1/*` est relayé
 * vers Kong par Next.js en local et par l'ALB sur AWS (ARCHITECTURE AD-07, D-069).
 * Il ne sert qu'à l'authentification : jamais d'accès aux tables depuis le navigateur.
 */
export function getBrowserSupabase(): SupabaseClient {
  client ??= createBrowserClient(window.location.origin, env.NEXT_PUBLIC_SUPABASE_ANON_KEY, {
    cookieOptions: AUTH_COOKIE_OPTIONS,
    auth: { lock: serialLock },
  });
  return client;
}

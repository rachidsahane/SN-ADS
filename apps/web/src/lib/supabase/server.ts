import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { env } from "@/lib/env";
import { AUTH_COOKIE_OPTIONS } from "@/lib/supabase/shared";

/**
 * Client Supabase côté serveur (route handlers, composants serveur). L'URL est celle que le conteneur `web`
 * atteint (NEXT_PUBLIC_SUPABASE_URL) ; le nom du cookie est le même que celui du navigateur.
 */
export async function createSupabaseServerClient(): Promise<SupabaseClient> {
  const cookieStore = await cookies();
  return createServerClient(env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_SUPABASE_ANON_KEY, {
    cookieOptions: AUTH_COOKIE_OPTIONS,
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (items) => {
        try {
          for (const { name, value, options } of items) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Rendu d'un composant serveur : les cookies sont en lecture seule. Le middleware rafraîchit la session.
        }
      },
    },
  });
}

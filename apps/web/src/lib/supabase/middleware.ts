import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { env } from "@/lib/env";
import { AUTH_COOKIE_OPTIONS } from "@/lib/supabase/shared";

/** Pages accessibles sans session. `/auth/set-password` n'en fait pas partie : elle exige la session de /auth/confirm. */
const PUBLIC_PATHS = new Set(["/login", "/forgot-password", "/auth/confirm"]);

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.has(pathname);
}

/**
 * Rafraîchit la session (cookies) et renvoie l'utilisateur validé par le serveur d'authentification.
 * `getUser()` interroge gotrue : on ne fait jamais confiance à `getSession()` côté serveur.
 * Une erreur réseau compte comme « pas d'utilisateur ».
 */
export async function updateSession(
  request: NextRequest,
): Promise<{ response: NextResponse; user: { id: string } | null }> {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    {
      cookieOptions: AUTH_COOKIE_OPTIONS,
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (items) => {
          for (const { name, value } of items) {
            request.cookies.set(name, value);
          }
          response = NextResponse.next({ request });
          for (const { name, value, options } of items) {
            response.cookies.set(name, value, options);
          }
        },
      },
    },
  );

  try {
    const { data, error } = await supabase.auth.getUser();
    return { response, user: error || !data.user ? null : { id: data.user.id } };
  } catch {
    return { response, user: null };
  }
}

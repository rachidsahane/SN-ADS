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
 * Une erreur réseau compte comme « pas d'utilisateur ». `disabled` est vrai quand gotrue refuse la session
 * parce que le compte est désactivé (code `user_banned`) : le middleware affiche alors le message de désactivation.
 */
export async function updateSession(
  request: NextRequest,
): Promise<{ response: NextResponse; user: { id: string } | null; disabled: boolean }> {
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
    if (error || !data.user) {
      return { response, user: null, disabled: error?.code === "user_banned" };
    }
    return { response, user: { id: data.user.id }, disabled: false };
  } catch {
    return { response, user: null, disabled: false };
  }
}

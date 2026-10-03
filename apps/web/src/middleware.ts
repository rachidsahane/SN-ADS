import { type NextRequest, NextResponse } from "next/server";

import { isPublicPath, updateSession } from "@/lib/supabase/middleware";

/** Redirection avec les cookies de session rafraîchis par `updateSession` (sinon la session serait perdue). */
function redirectTo(
  request: NextRequest,
  path: string,
  search: Record<string, string>,
  session: NextResponse,
): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = path;
  url.search = new URLSearchParams(search).toString();
  const redirect = NextResponse.redirect(url);
  for (const cookie of session.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  return redirect;
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { response, user } = await updateSession(request);
  const { pathname, search } = request.nextUrl;

  if (user || isPublicPath(pathname)) {
    return response;
  }
  if (pathname === "/auth/set-password") {
    // La page a besoin de la session créée par /auth/confirm : sans elle, le lien est invalide ou déjà utilisé.
    return redirectTo(request, "/login", { reason: "invalid_link" }, response);
  }
  return redirectTo(
    request,
    "/login",
    pathname === "/" ? {} : { next: `${pathname}${search}` },
    response,
  );
}

// Le middleware s'exécute AVANT les rewrites : /api/* et /auth/v1/* doivent en être exclus (pitfall P7).
export const config = {
  matcher: ["/((?!_next/|api/|auth/v1/|auth-templates/|healthz|icon\\.svg$|favicon\\.ico$).*)"],
};

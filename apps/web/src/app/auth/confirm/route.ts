import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { reportError } from "@/lib/observability";
import { safeNextPath } from "@/lib/redirect";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const LINK_TYPES = ["invite", "recovery"] as const;
type LinkType = (typeof LINK_TYPES)[number];

/** Redirection avec une adresse relative : indépendante de l'origine vue derrière l'ALB ou le conteneur. */
function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 302,
    headers: { Location: path, "Cache-Control": "no-store" },
  });
}

/**
 * Lien reçu par e-mail (invitation ou réinitialisation) : échange le jeton à usage unique contre une session
 * (cookies), puis envoie vers la page demandée. Tout échec mène à « Sign in » avec le message de lien invalide.
 * Le jeton n'est jamais répété dans une redirection ni dans un journal.
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const params = request.nextUrl.searchParams;
  const tokenHash = params.get("token_hash");
  const type = params.get("type");
  const invalid = redirectTo("/login?reason=invalid_link");

  if (!tokenHash || !LINK_TYPES.includes(type as LinkType)) {
    return invalid;
  }

  try {
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.verifyOtp({
      type: type as LinkType,
      token_hash: tokenHash,
    });
    if (error) {
      if (error.status === undefined || error.status >= 500) {
        reportError(error, { route: "/auth/confirm", linkType: type });
      }
      return invalid;
    }
  } catch (error) {
    reportError(error, { route: "/auth/confirm", linkType: type });
    return invalid;
  }
  return redirectTo(safeNextPath(params.get("next")));
}

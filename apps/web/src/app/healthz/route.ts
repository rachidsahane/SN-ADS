import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

/** Contrôle de santé du conteneur web (Docker, ALB). Ne dépend ni de l'API ni de la base. */
export function GET(): Response {
  return Response.json(
    { status: "ok", release: env.NEXT_PUBLIC_APP_RELEASE },
    { headers: { "Cache-Control": "no-store" } },
  );
}

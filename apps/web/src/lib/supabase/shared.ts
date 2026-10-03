import { env } from "@/lib/env";

/**
 * Options de cookie communes au navigateur, au serveur et au middleware (D-069). Le nom est fixe : par défaut,
 * @supabase/ssr le dérive de l'hôte de l'URL Supabase, qui diffère entre le navigateur et le serveur.
 * Les cookies restent lisibles par le navigateur (il envoie le jeton à l'API) : voir D-075.
 */
export const AUTH_COOKIE_OPTIONS = {
  name: "soronua-auth",
  sameSite: "lax" as const,
  secure: env.NEXT_PUBLIC_APP_ENV !== "local",
  path: "/",
};

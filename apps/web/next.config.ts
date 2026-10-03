import type { NextConfig } from "next";

// Exception documentée à "configuration lue uniquement dans src/lib/env.ts" (docs/decisions.md) :
// next.config.ts s'exécute avant l'application et ne peut pas importer src/lib/env.ts.
// API_PROXY_TARGET : local uniquement (ENV_SETUP.md section 3). Sur AWS, l'ALB route /api/*.
const apiProxyTarget = process.env.API_PROXY_TARGET;
// AUTH_PROXY_TARGET : local uniquement (D-069). Le navigateur ne parle qu'à sa propre origine : /auth/v1/* est
// relayé vers Kong. Sur AWS, l'ALB route /auth/v1/*.
const authProxyTarget = process.env.AUTH_PROXY_TARGET;

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // Les tests Playwright ouvrent le site via http://web:3000 (réseau Compose) : autorisé en développement.
  allowedDevOrigins: ["web"],
  async rewrites() {
    const rewrites: { source: string; destination: string }[] = [];
    if (apiProxyTarget) {
      rewrites.push({ source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*` });
    }
    if (authProxyTarget) {
      rewrites.push({
        source: "/auth/v1/:path*",
        destination: `${authProxyTarget}/auth/v1/:path*`,
      });
    }
    return rewrites;
  },
};

export default nextConfig;

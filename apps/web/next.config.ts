import type { NextConfig } from "next";

// Exception documentée à "configuration lue uniquement dans src/lib/env.ts" (docs/decisions.md) :
// next.config.ts s'exécute avant l'application et ne peut pas importer src/lib/env.ts.
// API_PROXY_TARGET : local uniquement (ENV_SETUP.md section 3). Sur AWS, l'ALB route /api/*.
const apiProxyTarget = process.env.API_PROXY_TARGET;

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // Les tests Playwright ouvrent le site via http://web:3000 (réseau Compose) : autorisé en développement.
  allowedDevOrigins: ["web"],
  async rewrites() {
    if (!apiProxyTarget) {
      return [];
    }
    return [{ source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*` }];
  },
};

export default nextConfig;

# syntax=docker/dockerfile:1.7
# Image web (Next.js). Contexte de construction : racine du dépôt (docker build -f apps/web/Dockerfile .).
# Cibles : dev (next dev, local), prod (standalone, ECS), e2e (Playwright, tests de bout en bout).
ARG NODE_IMAGE=node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c
ARG PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27

FROM ${NODE_IMAGE} AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

FROM base AS deps
COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

FROM deps AS dev
ENV NODE_ENV=development
COPY apps/web/ ./
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM deps AS build
# Variables publiques inscrites dans le code du navigateur : aucune valeur secrète (ENV_SETUP.md section 3).
ARG NEXT_PUBLIC_APP_ENV
ARG NEXT_PUBLIC_APP_RELEASE
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_SENTRY_DSN
# Relais same-origin /api et /auth/v1 : next.config.ts les lit à la CONSTRUCTION (sortie standalone). Vides sur AWS
# (l'ALB route), http://api:8000 et http://supabase-kong:8000 pour la démo locale (docker-compose.demo.yml).
ARG API_PROXY_TARGET=
ARG AUTH_PROXY_TARGET=
ENV API_PROXY_TARGET=${API_PROXY_TARGET} \
    AUTH_PROXY_TARGET=${AUTH_PROXY_TARGET}
ENV NEXT_PUBLIC_APP_ENV=${NEXT_PUBLIC_APP_ENV} \
    NEXT_PUBLIC_APP_RELEASE=${NEXT_PUBLIC_APP_RELEASE} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY} \
    NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN} \
    NODE_ENV=production
COPY apps/web/ ./
RUN --mount=type=cache,target=/app/.next/cache npm run build

FROM base AS prod
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/healthz').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "server.js"]

# La version de @playwright/test (package.json) doit être identique à celle de l'image.
FROM ${PLAYWRIGHT_IMAGE} AS e2e
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY apps/web/ ./
CMD ["npx", "playwright", "test"]

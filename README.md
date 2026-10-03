# Soro Nua Campaign Predictor

Internal tool of Soro Nua Agency (Douala): describe an online ad campaign, get predicted click-through rate, conversion rate and website visits, a performance level, the main drivers and up to three suggested changes.

Everything runs in Docker containers. Nothing is installed on the host except Docker, Make and git.

## Quick start

```
make env-local   # creates .env and deploy/supabase/.env, generates the local secrets (never overwrites a real value)
make build       # builds the images and pulls the pinned Supabase, Mailpit and pg_prove images
make up          # starts redis, api, web, Mailpit and the Supabase stack, waits until healthy, applies the migrations
```

- Web: http://localhost:3000 (port set by `WEB_HOST_PORT` in `.env`); the home page shows "API: healthy" and "Database: connected (schema <number>)"
- API health: http://localhost:8000/api/health, readiness: http://localhost:8000/api/ready (port set by `API_HOST_PORT`)
- Supabase gateway: http://localhost:54321 (`KONG_HTTP_PORT` in `deploy/supabase/.env`)
- Supabase Studio (local only, no login, `127.0.0.1` only): http://localhost:54323 (`STUDIO_HOST_PORT` in `deploy/supabase/.env`)
- Local mailbox (Mailpit): http://localhost:54324 (`MAILPIT_HOST_PORT` in `.env`)
- No Postgres port is published: `make db-shell` opens `psql` inside the database container.

`make db-reset` rebuilds the database and storage volumes of this project from scratch and replays every migration; `make test-db` runs the pgTAP tests.

`make help` lists every target. `make check` runs the full local gate; `make test-e2e` runs the Playwright scenarios.

## Documentation

Reference documents are in `docs/` (start with `docs/PROJECT_BRIEF.md` and `docs/ROADMAP.md`). Working rules for Claude Code are in `CLAUDE.md`. Decisions taken along the way are in `docs/decisions.md`.

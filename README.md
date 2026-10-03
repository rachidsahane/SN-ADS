# Soro Nua Campaign Predictor

Internal tool of Soro Nua Agency (Douala): describe an online ad campaign, get predicted click-through rate, conversion rate and website visits, a performance level, the main drivers and up to three suggested changes.

Everything runs in Docker containers. Nothing is installed on the host except Docker, Make and git.

## Quick start

```
make env-local   # creates .env from .env.example (never overwrites)
make build       # builds the images
make up          # starts redis, api and web and waits until they are healthy
```

- Web: http://localhost:3000 (port set by `WEB_HOST_PORT` in `.env`)
- API health: http://localhost:8000/api/health (port set by `API_HOST_PORT`)

`make help` lists every target. `make check` runs the full local gate; `make test-e2e` runs the Playwright scenarios.

## Documentation

Reference documents are in `docs/` (start with `docs/PROJECT_BRIEF.md` and `docs/ROADMAP.md`). Working rules for Claude Code are in `CLAUDE.md`. Decisions taken along the way are in `docs/decisions.md`.

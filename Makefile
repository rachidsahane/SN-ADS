SHELL := /bin/bash
.DEFAULT_GOAL := help

DC       := docker compose
PROFILES := --profile tools --profile e2e
TB       := $(DC) run --rm -T toolbox
API      := $(DC) run --rm --no-deps -T api
WEB      := $(DC) run --rm --no-deps -T web
NODE_IMAGE := node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c

.PHONY: help env-local build setup hooks pre-commit commit-msg up up-fresh down clean ps logs shell \
	toolbox-versions api-lock web-lock format format-check lint guards typecheck api-types \
	api-types-check test-unit test-integration test-db test-e2e audit secrets check

help: ## List the targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

env-local: ## Create .env from .env.example (never overwrites)
	@if [ -f .env ]; then echo ".env exists: left untouched"; else cp .env.example .env && echo ".env created from .env.example"; fi

build: ## Build api, web, e2e and toolbox images
	$(DC) $(PROFILES) build

setup: build hooks ## Build images and install git hooks
	@echo "setup done"

hooks: ## Install git hooks (plain sh calling make; nothing installed on the host)
	@mkdir -p .git/hooks
	@printf '%s\n' '#!/bin/sh' 'b=$$(git symbolic-ref --short -q HEAD)' 'case "$$b" in main|staging|dev) echo "Direct commits on $$b are forbidden: use phase/<NN>-<slug>"; exit 1;; esac' 'exec make --no-print-directory pre-commit' > .git/hooks/pre-commit
	@printf '%s\n' '#!/bin/sh' 'exec make --no-print-directory commit-msg MSG_FILE="$$1"' > .git/hooks/commit-msg
	@chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
	@echo "hooks installed"

pre-commit: ## Run the commit guards (staged files): secrets, forbidden files, format, lint
	$(TB) pre-commit run
	@$(MAKE) --no-print-directory format-check
	@$(MAKE) --no-print-directory lint

commit-msg: ## Check a commit message (MSG_FILE=path)
	@msg=$$(head -n1 "$(MSG_FILE)"); \
	if echo "$$msg" | grep -Eq '^(Merge |Revert ")'; then exit 0; fi; \
	if [ $${#msg} -le 72 ] && echo "$$msg" | grep -Eq '^(feat|fix|test|refactor|docs|chore|ci|build|perf|security)\((api|worker|web|db|ml|infra|ci|docs|e2e)\): [^ ]'; then exit 0; fi; \
	echo "Invalid commit message. Expected: <type>(<scope>): <summary>, first line <= 72 chars"; exit 1

up: env-local ## Start redis, api, web and wait until healthy
	$(DC) up -d --build --wait --wait-timeout 300 redis api web

up-fresh: env-local ## Same as up, renewing anonymous volumes (after a package-lock change)
	$(DC) up -d --build -V --wait --wait-timeout 300 redis api web

down: ## Stop the stack (volumes kept)
	$(DC) down --remove-orphans

clean: ## Stop and remove containers and volumes
	$(DC) $(PROFILES) down -v --remove-orphans

ps: ## Show containers
	$(DC) ps

logs: ## Follow logs (s=<service> optional)
	$(DC) logs -f --tail=200 $(s)

shell: ## Interactive shell in the toolbox
	$(DC) run --rm toolbox bash

toolbox-versions: ## Print the toolbox tool versions
	$(TB) sh -c 'python -V; uv --version; node -v; npm -v; supabase --version; aws --version; cdk --version; gitleaks version; pre-commit --version'

api-lock: ## Regenerate apps/api/uv.lock
	$(TB) sh -c 'cd apps/api && uv lock'

web-lock: ## Regenerate apps/web/package-lock.json (Node image, nothing on the host)
	docker run --rm -v "$(CURDIR)/apps/web":/app -w /app $(NODE_IMAGE) npm install --package-lock-only --ignore-scripts --no-audit --no-fund

format: ## Fix formatting (ruff, prettier)
	$(API) ruff format .
	$(WEB) npm run -s format

format-check: ## Check formatting only
	$(API) ruff format --check .
	$(WEB) npm run -s format:check

guards: ## Playwright version = image tag; no unjustified skip/only
	@v=$$(sed -n 's/.*"@playwright\/test": "\([^"]*\)".*/\1/p' apps/web/package.json); \
	grep -q "playwright:v$$v-noble" apps/web/Dockerfile || { echo "@playwright/test $$v differs from the Dockerfile image tag"; exit 1; }
	@if grep -rEn 'pytest\.mark\.skip|pytest\.skip\(|xfail|\.skip\(|\.only\(|test\.fixme|it\.todo' apps/api/tests apps/web/tests apps/web/e2e | grep -v 'D-[0-9]'; then echo "Unjustified skip/only (cite a decisions.md id like D-007)"; exit 1; fi

lint: guards ## Lint (ruff, eslint), compose config, lockfile consistency
	$(API) ruff check .
	$(WEB) npm run -s lint
	$(DC) config -q
	$(API) uv lock --check

typecheck: ## mypy --strict (apps/api/app) and tsc
	$(API) mypy
	$(WEB) npm run -s typecheck

api-types: ## Regenerate apps/web/src/lib/api/types.gen.ts from the running API
	$(DC) up -d --wait redis api
	$(WEB) npm run -s api-types

api-types-check: ## Fail if types.gen.ts is not up to date
	$(DC) up -d --wait redis api
	$(WEB) sh -c 'npx --no-install openapi-typescript "$${OPENAPI_URL:-http://api:8000/api/openapi.json}" -o /tmp/types.gen.ts > /dev/null && diff -u src/lib/api/types.gen.ts /tmp/types.gen.ts && echo "types.gen.ts is up to date"'

test-unit: ## pytest unit + Vitest (coverage thresholds)
	$(API) pytest tests/unit --cov --cov-fail-under=0 --cov-report=
	$(WEB) npm run -s test:coverage

test-integration: ## pytest integration (+ global api coverage gate 85 %)
	$(API) pytest tests/integration --cov --cov-append --cov-report=term-missing

test-db: ## pgTAP (no database before phase 1)
	@if ls supabase/migrations/*.sql > /dev/null 2>&1; then echo "Migrations exist: replace this guard with 'supabase test db' (phase 1)"; exit 1; else echo "SKIP test-db: no database before phase 1"; fi

test-e2e: ## Playwright (Chromium) against the running stack
	@$(MAKE) --no-print-directory up
	$(DC) --profile e2e run --rm e2e

audit: ## pip-audit + npm audit (api, web, root)
	$(API) sh -c 'uv export --frozen --no-hashes --no-emit-project -o /tmp/req.txt && pip-audit -r /tmp/req.txt --no-deps --disable-pip'
	$(WEB) sh -c 'npm run -s audit:prod && npm run -s audit:all'
	$(TB) sh -c 'npm audit --audit-level=high'

secrets: ## gitleaks over the git history
	$(TB) gitleaks git --redact --no-banner --verbose

check: ## Full local gate (stop at first failure)
	@echo "==> [1/9] up";             $(MAKE) --no-print-directory up
	@echo "==> [2/9] format-check";   $(MAKE) --no-print-directory format-check
	@echo "==> [3/9] lint";           $(MAKE) --no-print-directory lint
	@echo "==> [4/9] typecheck";      $(MAKE) --no-print-directory typecheck
	@echo "==> [5/9] api-types-check"; $(MAKE) --no-print-directory api-types-check
	@echo "==> [6/9] test-unit";      $(MAKE) --no-print-directory test-unit
	@echo "==> [7/9] test-integration"; $(MAKE) --no-print-directory test-integration
	@echo "==> [8/9] test-db";        $(MAKE) --no-print-directory test-db
	@echo "==> [9/9] audit";          $(MAKE) --no-print-directory audit

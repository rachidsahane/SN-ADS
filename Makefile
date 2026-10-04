SHELL := /bin/bash
.DEFAULT_GOAL := help

DC       := docker compose
PROFILES := --profile tools --profile e2e --profile notebooks --profile local
TB       := $(DC) run --rm -T toolbox
API      := $(DC) run --rm --no-deps -T api
WEB      := $(DC) run --rm --no-deps -T web
# deploy/supabase/generate_keys.py is outside apps/api: lint it with the api image and the api rules (read-only mount)
STACK_PY := $(DC) run --rm --no-deps -T -v "$(CURDIR)/deploy/supabase:/stack:ro" api
NODE_IMAGE := node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c

.PHONY: help env-local build setup hooks pre-commit commit-msg up up-fresh down clean ps logs shell \
	toolbox-versions api-lock web-lock format format-check lint guards typecheck api-types \
	api-types-check test-unit test-integration test-db test-e2e audit secrets check \
	db-reset db-migrate db-new-migration db-shell pull bootstrap-admin test-users seed demo demo-accounts \
	notebooks-run notebooks-lab

help: ## List the targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

env-local: ## Create .env and deploy/supabase/.env, generate the local secrets (never overwrites a real value)
	@if [ -f .env ]; then echo ".env exists: left untouched"; else cp .env.example .env && echo ".env created from .env.example"; fi
	@[ -f deploy/supabase/.env ] || cp deploy/supabase/.env.example deploy/supabase/.env
	@touch .demo-accounts.txt  # bind-mounted into `cli`: it must exist as a file (docker would create a folder)
	@# variables added to .env.example after .env was created (compose refuses to start without them): append them, generate_keys.py then settles the placeholders
	@while IFS= read -r line; do case "$$line" in [A-Z]*=*) name=$${line%%=*}; grep -q "^$$name=" deploy/supabase/.env || { echo "$$line" >> deploy/supabase/.env; echo "deploy/supabase/.env: $$name added"; };; esac; done < deploy/supabase/.env.example
	@$(DC) run --rm -T --user "$$(id -u):$$(id -g)" toolbox python deploy/supabase/generate_keys.py --env local

build: env-local ## Build api, web, e2e and toolbox images, pull the pinned Supabase images
	$(DC) $(PROFILES) build
	$(DC) $(PROFILES) pull --ignore-buildable --quiet

pull: env-local ## Pull the pinned images that are not built here (Supabase stack, Mailpit, pg_prove)
	$(DC) $(PROFILES) pull --ignore-buildable

setup: build hooks ## Build images and install git hooks
	@echo "setup done"

hooks: ## Install git hooks (plain sh calling make; nothing installed on the host)
	@mkdir -p .git/hooks
	@printf '%s\n' '#!/bin/sh' 'b=$$(git symbolic-ref --short -q HEAD)' 'case "$$b" in main|staging|dev) echo "Direct commits on $$b are forbidden: use phase/<NN>-<slug>"; exit 1;; esac' 'exec make --no-print-directory pre-commit' > .git/hooks/pre-commit
	@printf '%s\n' '#!/bin/sh' 'exec make --no-print-directory commit-msg MSG_FILE="$$1"' > .git/hooks/commit-msg
	@chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
	@echo "hooks installed"

pre-commit: env-local ## Run the commit guards (staged files): secrets, forbidden files, format, lint
	$(TB) pre-commit run --all-files
	@$(MAKE) --no-print-directory format-check
	@$(MAKE) --no-print-directory lint

commit-msg: ## Check a commit message (MSG_FILE=path)
	@msg=$$(head -n1 "$(MSG_FILE)"); \
	if echo "$$msg" | grep -Eq '^(Merge |Revert ")'; then exit 0; fi; \
	if [ $${#msg} -le 72 ] && echo "$$msg" | grep -Eq '^(feat|fix|test|refactor|docs|chore|ci|build|perf|security)\((api|worker|web|db|ml|infra|ci|docs|e2e)\): [^ ]'; then exit 0; fi; \
	echo "Invalid commit message. Expected: <type>(<scope>): <summary>, first line <= 72 chars"; exit 1

up: env-local ## Start the whole local stack (redis, api, web, Mailpit, Supabase), wait until healthy, apply the migrations
	$(DC) --profile local up -d --build --wait --wait-timeout 300
	@$(MAKE) --no-print-directory db-migrate

up-fresh: env-local ## Same as up, renewing anonymous volumes (after a package-lock change)
	$(DC) --profile local up -d --build -V --wait --wait-timeout 300
	@$(MAKE) --no-print-directory db-migrate

down: ## Stop the stack (volumes kept)
	$(DC) --profile local down --remove-orphans

db-migrate: ## Apply the pending migrations (supabase/migrations) to the running database; idempotent
	$(TB) sh -c 'supabase migration up --db-url "$$DATABASE_URL"'

db-new-migration: ## Create an empty migration: make db-new-migration name=<description_snake_case>
	@test -n "$(name)" || { echo "usage: make db-new-migration name=<description_snake_case>"; exit 1; }
	$(TB) sh -c 'supabase migration new $(name)'

db-reset: env-local ## Rebuild the database and storage volumes of this project from scratch, then migrate
	$(DC) --profile local rm -sf supabase-kong supabase-studio supabase-meta supabase-storage supabase-rest supabase-auth supabase-db
	@for volume in supabase-db-data supabase-db-config supabase-storage-data; do \
		ids=$$(docker volume ls -q --filter label=com.docker.compose.project=soronua-predict --filter label=com.docker.compose.volume=$$volume); \
		if [ -n "$$ids" ]; then docker volume rm -f $$ids > /dev/null && echo "volume $$volume removed"; fi; \
	done
	$(DC) --profile local up -d --wait --wait-timeout 300 supabase-db supabase-auth supabase-rest supabase-storage supabase-kong supabase-meta supabase-studio
	@$(MAKE) --no-print-directory db-migrate

bootstrap-admin: env-local ## Create or re-invite the first administrator: make bootstrap-admin FIRST_ADMIN_EMAIL=a@b.test FIRST_ADMIN_FULL_NAME="Name" [PRINT_LINK=1]
	$(DC) --profile tools run --rm -T cli python -m app.cli.bootstrap_admin $(if $(PRINT_LINK),--print-link)

test-users: env-local ## Create or reset the local Playwright accounts (refused when APP_ENV=production)
	$(DC) --profile tools run --rm -T cli python -m app.cli.create_test_users

seed: env-local ## Load the 8 000 seed rows into dataset_rows (idempotent)
	$(DC) --profile tools run --rm -T cli python -m app.cli.seed_dataset

demo-accounts: env-local ## Create the demo admin and marketer (passwords generated once in .demo-accounts.txt)
	$(DC) --profile tools run --rm -T cli python -m app.cli.demo_accounts

demo: ## One command for the presentation: start everything, load the data, create the accounts, train and activate a model
	@$(MAKE) --no-print-directory up
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory demo-accounts
	$(DC) --profile tools run --rm -T cli python -m app.cli.train_demo
	@echo ""
	@echo "Demo ready: http://localhost:$$(sed -n "s/^WEB_HOST_PORT=//p" .env | head -1 | grep . || echo 3000)   (accounts below, also in .demo-accounts.txt)"
	@cat .demo-accounts.txt

db-shell: ## psql in the database container (no port is published on the host)
	$(DC) exec supabase-db psql -U postgres -d postgres

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
	$(STACK_PY) ruff format --no-cache --check --config /app/pyproject.toml /stack/generate_keys.py
	$(WEB) npm run -s format:check

guards: env-local ## Playwright version = image tag; no unjustified skip/only; resolved compose guards (digests, secrets, ports)
	@v=$$(sed -n 's/.*"@playwright\/test": "\([^"]*\)".*/\1/p' apps/web/package.json); \
	grep -q "playwright:v$$v-noble" apps/web/Dockerfile || { echo "@playwright/test $$v differs from the Dockerfile image tag"; exit 1; }
	@if grep -rEn 'pytest\.mark\.skip|pytest\.skip\(|xfail|\.skip\(|\.only\(|test\.fixme|it\.todo' apps/api/tests apps/web/tests apps/web/e2e | grep -v 'D-[0-9]'; then echo "Unjustified skip/only (cite a decisions.md id like D-007)"; exit 1; fi
	@# The resolved configuration holds secrets: it is only piped into the checker, never printed (only the verdicts are).
	@set -o pipefail; $(DC) --profile local --profile tools config --format json | $(TB) python deploy/supabase/tests/compose_guards.py

lint: env-local guards ## Lint (ruff, eslint), compose config, lockfile consistency
	$(API) ruff check .
	$(STACK_PY) sh -c 'ruff check --no-cache --config /app/pyproject.toml /stack/generate_keys.py && mypy --config-file /app/pyproject.toml --cache-dir=/dev/null /stack/generate_keys.py'
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
	$(TB) python -m unittest discover -s deploy/supabase/tests -t . -v

test-integration: ## pytest integration (+ global api coverage gate 85 %)
	$(API) pytest tests/integration --cov --cov-append --cov-report=term-missing

PGPROVE_FLAGS ?=

test-db: ## pgTAP: apply migrations, then run supabase/tests/database/*.test.sql with pg_prove (PGPROVE_FLAGS=--verbose for detail)
	@ls supabase/tests/database/*.test.sql > /dev/null 2>&1 || { echo "test-db: no pgTAP test found in supabase/tests/database"; exit 1; }
	@$(MAKE) --no-print-directory db-migrate
	$(DC) exec -T supabase-db psql -U supabase_admin -d postgres -v ON_ERROR_STOP=1 -c "create extension if not exists pgtap with schema extensions"
	$(DC) --profile tools run --rm -T pgtap -h supabase-db -U postgres -d postgres --ext .sql $(PGPROVE_FLAGS) /tests

test-e2e: ## Playwright on a freshly RESET local stack (wipes this project's local database, then creates the test accounts)
	@$(MAKE) --no-print-directory up
	@$(MAKE) --no-print-directory db-reset
	@$(MAKE) --no-print-directory test-users
	$(DC) --profile e2e run --rm e2e

audit: ## pip-audit + npm audit (api, web, root)
	$(API) sh -c 'uv export --frozen --no-hashes --no-emit-project --all-groups -o /tmp/req.txt && pip-audit -r /tmp/req.txt --no-deps --disable-pip'
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

notebooks-run: ## Execute the three notebooks in Docker (outputs saved in place; HTML copies in notebooks/_out)
	$(DC) --profile notebooks run --rm -T notebooks sh -c 'mkdir -p _out && for n in 01_data_profile 02_train_three_models 03_evaluation_and_scoring; do jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 $$n.ipynb || exit 1; jupyter nbconvert --to html --output-dir _out $$n.ipynb || exit 1; done'

notebooks-lab: ## JupyterLab on 127.0.0.1:8888 (token printed in the console)
	$(DC) --profile notebooks run --rm --service-ports notebooks

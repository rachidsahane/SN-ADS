"""Guards on the RESOLVED compose configuration (phase 1, spec 3.G / 2.D `guards`). Not collected by unittest.

Usage (from the repository root; the resolved configuration contains secrets, so it is only piped, never printed):

    docker compose --profile local --profile tools config --format json \
      | docker compose run --rm -T toolbox python deploy/supabase/tests/compose_guards.py

Exit code 0 when every guard holds, 1 otherwise. Only the guard verdicts are printed, never a value.
`docker compose config` itself failing (for example `include` pointing at a missing deploy/supabase/.env, or a
`${VAR:?}` secret left empty) fails the pipeline: that is the "compose config validates with the include" check.

Guards:
  G0  the stack services and mailpit/pgtap exist in the resolved config (the include works)
  G1  every image not built by the repository is pinned by `@sha256:<64 hex>`
  G2  `web` and `e2e` carry no variable whose name contains SERVICE, JWT, POSTGRES or ROLE_KEY (CLAUDE 4.2, D-010),
      and no Supabase variable at all in phase 1; the service role key value never appears in their environment
  G3  no port is published outside 127.0.0.1; supabase-db, -rest, -storage, -meta, -auth, pgtap, toolbox publish none
  G4  the service role key is only given to the closed list of services (api and cli since phase 2, D-072;
      never web/e2e/stack apps)
  G5  SUPABASE_JWT_SECRET only reaches the api (never web, e2e or cli; phase 2)
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
FORBIDDEN_NAME = re.compile(r"SERVICE|JWT|POSTGRES|ROLE_KEY")
REQUIRED_SERVICES = (
    "supabase-db",
    "supabase-auth",
    "supabase-rest",
    "supabase-storage",
    "supabase-kong",
    "supabase-meta",
    "supabase-studio",
    "mailpit",
    "pgtap",
)
NO_PORT_SERVICES = (
    "supabase-db",
    "supabase-auth",
    "supabase-rest",
    "supabase-storage",
    "supabase-meta",
    "pgtap",
    "toolbox",
    "redis",
    "cli",
)
SERVICE_KEY_HOLDERS = {"api", "cli"}  # phase 2 (D-072); the worker joins the list in a later phase
JWT_SECRET_VARIABLE = "SUPABASE_JWT_SECRET"
JWT_SECRET_HOLDERS = {"api"}
LOOPBACK = {"127.0.0.1"}


def main() -> int:
    try:
        config: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("FAIL G-input: stdin is not the JSON of `docker compose config --format json`")
        return 1
    services: dict[str, dict[str, Any]] = config.get("services", {})
    failures: list[str] = []

    for name in REQUIRED_SERVICES:
        if name not in services:
            failures.append(f"G0: service {name} is missing from the resolved configuration")

    for name, service in sorted(services.items()):
        image = service.get("image", "")
        if service.get("build") is None and not DIGEST.search(image):
            failures.append(f"G1: {name} image is not pinned by digest")

    for name in ("web", "e2e"):
        env = (services.get(name) or {}).get("environment") or {}
        for var in env:
            if FORBIDDEN_NAME.search(var) or var.startswith("SUPABASE_"):
                failures.append(f"G2: {name} receives the forbidden variable {var}")

    for name, service in sorted(services.items()):
        for port in service.get("ports") or []:
            host_ip = port.get("host_ip", "")
            if host_ip not in LOOPBACK:
                failures.append(f"G3: {name} publishes port {port.get('target')} outside 127.0.0.1")
        if name in NO_PORT_SERVICES and service.get("ports"):
            failures.append(f"G3: {name} must not publish any port")

    service_key = ""
    api_env = (services.get("api") or {}).get("environment") or {}
    if isinstance(api_env.get("SUPABASE_SERVICE_ROLE_KEY"), str):
        service_key = api_env["SUPABASE_SERVICE_ROLE_KEY"]
    for name, service in sorted(services.items()):
        env = service.get("environment") or {}
        for var, value in env.items():
            holds_key = var == "SUPABASE_SERVICE_ROLE_KEY" or (bool(service_key) and value == service_key)
            if holds_key and name not in SERVICE_KEY_HOLDERS and not name.startswith("supabase-"):
                failures.append(f"G4: {name} receives the service role key through {var}")

    for name, service in sorted(services.items()):
        env = service.get("environment") or {}
        if JWT_SECRET_VARIABLE in env and name not in JWT_SECRET_HOLDERS:
            failures.append(f"G5: {name} receives {JWT_SECRET_VARIABLE} (api only)")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"compose guards: {len(failures)} violation(s)")
        return 1
    print("compose guards: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

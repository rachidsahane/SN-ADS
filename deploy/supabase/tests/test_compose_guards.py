"""The resolved-configuration guards must really detect violations (a guard that never fails proves nothing)."""

from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from typing import Any

from . import compose_guards

DIGEST = "@sha256:" + "a" * 64


def good_config() -> dict[str, Any]:
    stack = {
        name: {"image": f"example.test/{name}:1{DIGEST}"}
        for name in (
            "supabase-db",
            "supabase-auth",
            "supabase-rest",
            "supabase-storage",
            "supabase-meta",
            "mailpit",
            "pgtap",
            "toolbox",
            "redis",
        )
    }
    stack["supabase-kong"] = {
        "image": f"example.test/kong:2{DIGEST}",
        "ports": [{"host_ip": "127.0.0.1", "target": 8000, "published": "54321"}],
        "environment": {"SUPABASE_SERVICE_KEY": "dummy-service-key"},
    }
    stack["supabase-studio"] = {
        "image": f"example.test/studio:1{DIGEST}",
        "ports": [{"host_ip": "127.0.0.1", "target": 3000, "published": "54323"}],
    }
    stack["api"] = {
        "build": {"context": "."},
        "image": "soronua-predict-api:dev",
        "environment": {"SUPABASE_SERVICE_ROLE_KEY": "dummy-service-key", "SUPABASE_ANON_KEY": "dummy-anon"},
    }
    stack["web"] = {
        "build": {"context": "."},
        "image": "soronua-predict-web:dev",
        "environment": {"NEXT_PUBLIC_APP_ENV": "local"},
        "ports": [{"host_ip": "127.0.0.1", "target": 3000, "published": "3000"}],
    }
    stack["e2e"] = {"build": {"context": "."}, "image": "soronua-predict-web-e2e:local", "environment": {}}
    stack["cli"] = {  # phase 2 (D-072): closed-list holder of the service key, no port
        "build": {"context": "."},
        "image": "soronua-predict-api:dev",
        "environment": {"SUPABASE_SERVICE_ROLE_KEY": "dummy-service-key", "SUPABASE_ANON_KEY": "dummy-anon"},
    }
    return {"services": stack}


def run_guards(config: dict[str, Any]) -> tuple[int, str]:
    stdin, stdout = sys.stdin, io.StringIO()
    sys.stdin = io.StringIO(json.dumps(config))
    try:
        with redirect_stdout(stdout):
            code = compose_guards.main()
    finally:
        sys.stdin = stdin
    return code, stdout.getvalue()


class ComposeGuardsSelfTest(unittest.TestCase):
    def test_a_compliant_configuration_passes(self) -> None:
        code, out = run_guards(good_config())
        self.assertEqual(code, 0, out)

    def test_missing_stack_service_is_reported(self) -> None:
        config = good_config()
        del config["services"]["supabase-db"]
        self.assertIn("G0", run_guards(config)[1])

    def test_unpinned_image_is_reported(self) -> None:
        config = good_config()
        config["services"]["mailpit"]["image"] = "example.test/mailpit:latest"
        self.assertIn("G1", run_guards(config)[1])

    def test_web_secret_variable_is_reported(self) -> None:
        for var in ("SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET", "POSTGRES_PASSWORD", "SOME_ROLE_KEY", "SUPABASE_URL"):
            with self.subTest(var=var):
                config = copy.deepcopy(good_config())
                config["services"]["web"]["environment"][var] = "x"
                code, out = run_guards(config)
                self.assertEqual(code, 1)
                self.assertIn("G2", out)

    def test_port_outside_loopback_is_reported(self) -> None:
        config = good_config()
        config["services"]["web"]["ports"][0]["host_ip"] = "0.0.0.0"
        self.assertIn("G3", run_guards(config)[1])

    def test_database_port_is_reported_even_on_loopback(self) -> None:
        config = good_config()
        config["services"]["supabase-db"]["ports"] = [{"host_ip": "127.0.0.1", "target": 5432, "published": "54322"}]
        self.assertIn("G3", run_guards(config)[1])

    def test_service_key_in_another_service_is_reported(self) -> None:
        config = good_config()
        config["services"]["e2e"]["environment"] = {"KEY_COPY": "dummy-service-key"}
        self.assertIn("G4", run_guards(config)[1])

    def test_cli_may_hold_the_service_key(self) -> None:
        """Phase 2: the closed list of service-key holders is api + cli (ARCHITECTURE 2.5, D-072)."""
        code, out = run_guards(good_config())
        self.assertEqual(code, 0, out)
        self.assertNotIn("G4", out)

    def test_a_service_not_in_the_closed_list_is_still_refused_the_key(self) -> None:
        config = good_config()
        config["services"]["worker-like"] = {
            "build": {"context": "."},
            "image": "x:dev",
            "environment": {"SUPABASE_SERVICE_ROLE_KEY": "dummy-service-key"},
        }
        code, out = run_guards(config)
        self.assertEqual(code, 1)
        self.assertIn("G4: worker-like", out)

    def test_cli_publishing_a_port_is_reported(self) -> None:
        config = good_config()
        config["services"]["cli"]["ports"] = [{"host_ip": "127.0.0.1", "target": 8000, "published": "8001"}]
        code, out = run_guards(config)
        self.assertEqual(code, 1)
        self.assertIn("G3: cli must not publish any port", out)

    def test_jwt_secret_variable_is_reported_outside_the_api(self) -> None:
        """G5: SUPABASE_JWT_SECRET only reaches `api` (never web, e2e, cli)."""
        for name in ("web", "e2e", "cli"):
            with self.subTest(service=name):
                config = copy.deepcopy(good_config())
                config["services"][name]["environment"]["SUPABASE_JWT_SECRET"] = "dummy-jwt-secret"
                code, out = run_guards(config)
                self.assertEqual(code, 1, out)
                self.assertIn("G5", out)
                self.assertNotIn("dummy-jwt-secret", out)

    def test_api_may_hold_the_jwt_secret(self) -> None:
        config = good_config()
        config["services"]["api"]["environment"]["SUPABASE_JWT_SECRET"] = "dummy-jwt-secret"
        code, out = run_guards(config)
        self.assertEqual(code, 0, out)

    def test_the_public_anon_key_mapping_is_the_only_supabase_name_web_may_carry(self) -> None:
        """Phase 2: web gets NEXT_PUBLIC_SUPABASE_URL/ANON_KEY (public values); any other SUPABASE_* name stays refused."""
        config = good_config()
        config["services"]["web"]["environment"].update(
            {"NEXT_PUBLIC_SUPABASE_URL": "http://supabase-kong:8000", "NEXT_PUBLIC_SUPABASE_ANON_KEY": "dummy-anon"}
        )
        code, out = run_guards(config)
        self.assertEqual(code, 0, out)
        config["services"]["web"]["environment"]["SUPABASE_ANON_KEY"] = "dummy-anon"
        code, out = run_guards(config)
        self.assertEqual(code, 1)
        self.assertIn("G2", out)

    def test_verdict_never_prints_a_value(self) -> None:
        config = good_config()
        config["services"]["web"]["environment"]["JWT_SECRET"] = "dummy-service-key"
        self.assertNotIn("dummy-service-key", run_guards(config)[1])


if __name__ == "__main__":
    unittest.main()

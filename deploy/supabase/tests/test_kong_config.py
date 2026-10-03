"""kong.yml routes match the phase 1 spec (2.A.3; ARCHITECTURE 2.4). Static analysis, no container needed.

kong.yml is evaluated by the container entrypoint with `eval "echo ..."`, so any `$` other than the three
variables below would be rewritten: that is checked too (pitfall P9).
"""

from __future__ import annotations

import re
import unittest
from typing import Any

from ._helpers import KONG_YML, load_yaml

ALLOWED_VARIABLES = {"SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SITE_URL"}
ALLOWED_PLUGINS = {"cors", "key-auth", "acl", "request-termination"}
EXPECTED_ROUTES = {
    "auth-v1-open": ("http://supabase-auth:9999/verify", ["/auth/v1/verify"]),
    "auth-v1": ("http://supabase-auth:9999/", ["/auth/v1/"]),
    "rest-v1": ("http://supabase-rest:3000/", ["/rest/v1/"]),
    "storage-v1": ("http://supabase-storage:5000/", ["/storage/v1/"]),
}
FORBIDDEN_UPSTREAMS = ("meta", "studio", "realtime", "functions", "analytics", "graphql", "/pg", "imgproxy")
CORS_HEADERS = {"apikey", "authorization", "content-type", "x-client-info", "x-supabase-api-version"}


def plugins_of(service: dict[str, Any]) -> list[dict[str, Any]]:
    found = list(service.get("plugins") or [])
    for route in service.get("routes") or []:
        found.extend(route.get("plugins") or [])
    return found


class KongDeclarativeConfigTest(unittest.TestCase):
    config: dict[str, Any]
    services: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_yaml(KONG_YML)
        cls.services = {s["name"]: s for s in cls.config["services"]}

    def test_declarative_format(self) -> None:
        self.assertEqual(str(self.config["_format_version"]), "2.1")
        self.assertIs(self.config["_transform"], True)

    def test_only_the_three_shell_variables_appear_in_the_file(self) -> None:
        text = KONG_YML.read_text(encoding="utf-8")
        self.assertNotIn("$(", text, "no command substitution or Lua expression (the entrypoint evals the file)")
        used = set(re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", text))
        self.assertEqual(used, ALLOWED_VARIABLES)
        self.assertNotRegex(text, r"\$(?![A-Za-z_{])", "a lone `$` would be rewritten by the entrypoint")

    def test_exactly_the_five_expected_services(self) -> None:
        self.assertEqual(set(self.services), {*EXPECTED_ROUTES, "kong-health"})

    def test_upstreams_and_paths(self) -> None:
        for name, (url, paths) in EXPECTED_ROUTES.items():
            with self.subTest(service=name):
                service = self.services[name]
                self.assertEqual(service["url"], url)
                route_paths = [p for route in service["routes"] for p in route["paths"]]
                self.assertEqual(route_paths, paths)

    def test_verify_route_is_open_and_strips_the_path(self) -> None:
        service = self.services["auth-v1-open"]
        for route in service["routes"]:
            self.assertIs(route.get("strip_path"), True)
        names = [p["name"] for p in plugins_of(service)]
        self.assertEqual(names, ["cors"], "the e-mail link is clicked without any key: cors only")

    def test_other_routes_are_strip_path_and_require_a_key_with_acl(self) -> None:
        for name in ("auth-v1", "rest-v1", "storage-v1"):
            with self.subTest(service=name):
                service = self.services[name]
                for route in service["routes"]:
                    self.assertIs(route.get("strip_path"), True)
                plugins = {p["name"]: p for p in plugins_of(service)}
                self.assertEqual(set(plugins), {"cors", "key-auth", "acl"})
                self.assertIs(plugins["key-auth"]["config"].get("hide_credentials"), False)
                self.assertEqual(sorted(plugins["acl"]["config"]["allow"]), ["admin", "anon"])

    def test_kong_health_answers_200_ok_without_upstream_call(self) -> None:
        service = self.services["kong-health"]
        paths = [p for route in service["routes"] for p in route["paths"]]
        self.assertEqual(paths, ["/kong-health"])
        plugins = {p["name"]: p for p in plugins_of(service)}
        self.assertEqual(set(plugins), {"request-termination"})
        self.assertEqual(plugins["request-termination"]["config"]["status_code"], 200)
        self.assertEqual(plugins["request-termination"]["config"]["message"], "OK")

    def test_consumers_keys_and_acl_groups(self) -> None:
        consumers = {c["username"]: c for c in self.config["consumers"]}
        self.assertEqual(set(consumers), {"anon", "service_role"})
        self.assertEqual(consumers["anon"]["keyauth_credentials"][0]["key"], "$SUPABASE_ANON_KEY")
        self.assertEqual(consumers["service_role"]["keyauth_credentials"][0]["key"], "$SUPABASE_SERVICE_KEY")
        acls = {a["consumer"]: a["group"] for a in self.config["acls"]}
        self.assertEqual(acls, {"anon": "anon", "service_role": "admin"})

    def test_cors_is_limited_to_the_site(self) -> None:
        cors_plugins = [p for s in self.services.values() for p in plugins_of(s) if p["name"] == "cors"]
        self.assertTrue(cors_plugins)
        for plugin in cors_plugins:
            config = plugin["config"]
            self.assertIn("$SITE_URL", config["origins"])
            self.assertNotIn("*", config["origins"])
            self.assertIs(config["credentials"], True)
            self.assertTrue(CORS_HEADERS <= {h.lower() for h in config["headers"]})

    def test_only_the_planned_plugins_are_used(self) -> None:
        used = {p["name"] for s in self.services.values() for p in plugins_of(s)}
        self.assertLessEqual(used, ALLOWED_PLUGINS)
        self.assertNotIn("request-transformer", used)

    def test_no_route_to_internal_or_unplanned_services(self) -> None:
        for name, service in self.services.items():
            for word in FORBIDDEN_UPSTREAMS:
                self.assertNotIn(word, service.get("url", ""), f"{name} must not proxy to {word}")
            for route in service.get("routes") or []:
                for path in route["paths"]:
                    self.assertNotRegex(path, r"^/(pg|graphql|realtime|functions|analytics|mcp)\b")

    def test_no_oauth_or_saml_route_in_phase_1(self) -> None:
        text = KONG_YML.read_text(encoding="utf-8")
        for word in ("callback", "authorize", "jwks", "sso", "saml"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()

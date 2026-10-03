"""Static checks of docker-compose.yml (root) and deploy/supabase/docker-compose.yml (phase 1, spec 2.A, 2.B).

No Docker needed: the YAML is analysed as written (interpolation is checked by tests/compose_guards.py on the
resolved configuration, wired into `make guards`). Image tags and digests are copied from spec section 0.
"""

from __future__ import annotations

import re
import unittest
from typing import Any

from ._helpers import (
    COMPOSE_REF,
    ENV_EXAMPLE,
    ROOT_COMPOSE,
    STACK_COMPOSE,
    environment_of,
    load_yaml,
    parse_env_file,
)

PINNED = {
    "supabase-db": "public.ecr.aws/supabase/postgres:17.6.1.159@sha256:86a2e078779e5bdccda1f6f6c5063aa9779a322d1fface5fb408d051909b230f",
    "supabase-auth": "public.ecr.aws/supabase/gotrue:v2.195.0@sha256:362659ca70eaa75ba05bbaf963caa84c1c5afe5e8fbf0777e17b830dd5f0f60a",
    "supabase-rest": "public.ecr.aws/supabase/postgrest:v16.1@sha256:5922bde07147b82b1c9d8f749e48c1e5b99ebb233f3888bb7ab65f07cf4ac82d",
    "supabase-kong": "public.ecr.aws/supabase/kong:2.8.1@sha256:1b53405d8680a09d6f44494b7990bf7da2ea43f84a258c59717d4539abf09f6d",
    "supabase-meta": "public.ecr.aws/supabase/postgres-meta:v0.98.0@sha256:cef71ba901751dcc242cc685cf13786935ea8926820fb342f23bb0fbef77de5a",
    "supabase-studio": "public.ecr.aws/supabase/studio:2026.08.17-sha-0c1da8f@sha256:08dc77f12e08faacc55960fef1dce37fa73d16acb52abeb216aa23dc5e70824b",
    "supabase-storage": "public.ecr.aws/supabase/storage-api:v1.74.0@sha256:f1546fac6d1c7e345428ac904bfaa7be7cecd50a1f549fe1cf38c628a7b15c85",
}
MAILPIT_IMAGE = "public.ecr.aws/supabase/mailpit:v1.30.2@sha256:37a38e48e9338cd7e89dfeb487f37b02ebfcd9cb23111bed2d345e79d37d6dd6"
PGTAP_IMAGE = "public.ecr.aws/supabase/pg_prove:3.36@sha256:eda7c5e68719e9c8287e78c017118407b48df904a51c935f5ab6098b8c0bc6bc"
STACK_SERVICES = set(PINNED)
LOCAL_ONLY = {"supabase-meta", "supabase-studio"}
STACK_SECRETS = ("POSTGRES_PASSWORD", "JWT_SECRET", "ANON_KEY", "SERVICE_ROLE_KEY", "PG_META_CRYPTO_KEY")
FORBIDDEN_WEB_NAME = re.compile(r"SERVICE|JWT|POSTGRES|ROLE_KEY")


def published(service: dict[str, Any]) -> list[str]:
    return [str(p) for p in service.get("ports") or []]


class StackComposeTest(unittest.TestCase):
    compose: dict[str, Any]
    services: dict[str, dict[str, Any]]
    text: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = load_yaml(STACK_COMPOSE)
        cls.services = cls.compose["services"]
        cls.text = STACK_COMPOSE.read_text(encoding="utf-8")

    def test_service_names_are_exactly_the_planned_ones(self) -> None:
        self.assertEqual(set(self.services), STACK_SERVICES)

    def test_no_project_name_and_no_container_name(self) -> None:
        self.assertNotIn("name", self.compose, "the project name is fixed by the root compose file")
        for name, service in self.services.items():
            self.assertNotIn("container_name", service, f"{name}: container_name would collide with other projects")

    def test_images_are_pinned_by_digest_to_the_chosen_versions(self) -> None:
        for name, image in PINNED.items():
            self.assertEqual(self.services[name]["image"], image, name)

    def test_meta_and_studio_are_local_only(self) -> None:
        for name, service in self.services.items():
            expected = ["local"] if name in LOCAL_ONLY else None
            self.assertEqual(service.get("profiles"), expected, name)

    def test_every_service_restarts_and_has_a_healthcheck(self) -> None:
        for name, service in self.services.items():
            self.assertEqual(service.get("restart"), "unless-stopped", name)
            self.assertIn("test", service.get("healthcheck", {}), f"{name}: healthcheck required")

    def test_environment_is_an_explicit_list_never_env_file(self) -> None:
        for name, service in self.services.items():
            self.assertNotIn("env_file", service, name)
            self.assertTrue(service.get("environment"), f"{name}: explicit environment required")

    def test_only_kong_and_studio_publish_a_port(self) -> None:
        for name in ("supabase-db", "supabase-auth", "supabase-rest", "supabase-storage", "supabase-meta"):
            self.assertEqual(published(self.services[name]), [], f"{name} must publish no port")
        (kong_port,) = published(self.services["supabase-kong"])
        self.assertEqual(kong_port, "${KONG_BIND_ADDRESS:-127.0.0.1}:${KONG_HTTP_PORT:-54321}:8000")
        (studio_port,) = published(self.services["supabase-studio"])
        self.assertEqual(studio_port, "127.0.0.1:${STUDIO_HOST_PORT:-54323}:3000")

    def test_named_volumes(self) -> None:
        self.assertEqual(set(self.compose["volumes"]), {"supabase-db-data", "supabase-db-config", "supabase-storage-data"})
        db_volumes = " ".join(str(v) for v in self.services["supabase-db"]["volumes"])
        self.assertIn("supabase-db-data:/var/lib/postgresql/data", db_volumes)
        self.assertIn("supabase-db-config:/etc/postgresql-custom", db_volumes)
        self.assertIn("./db/roles.sql:/docker-entrypoint-initdb.d/init-scripts/99-roles.sql:ro", db_volumes)
        self.assertIn("./db/jwt.sql:/docker-entrypoint-initdb.d/init-scripts/99-jwt.sql:ro", db_volumes)
        storage_volumes = " ".join(str(v) for v in self.services["supabase-storage"]["volumes"])
        self.assertIn("supabase-storage-data:/var/lib/storage", storage_volumes)

    def test_db_healthcheck_waits_for_the_init_scripts(self) -> None:
        test = " ".join(self.services["supabase-db"]["healthcheck"]["test"])
        self.assertIn("pg_isready", test)
        self.assertIn("-h localhost", test, "the TCP check only passes once init scripts are done")

    def test_dependencies_wait_for_a_healthy_database(self) -> None:
        for name in ("supabase-auth", "supabase-rest", "supabase-storage"):
            depends = self.services[name]["depends_on"]
            self.assertEqual(depends["supabase-db"]["condition"], "service_healthy", name)

    def test_auth_security_settings(self) -> None:
        env = environment_of(self.services["supabase-auth"])
        self.assertEqual(env["GOTRUE_DISABLE_SIGNUP"], "true")  # fixed value, not a variable (ARCHITECTURE 2.4)
        self.assertEqual(env["GOTRUE_EXTERNAL_EMAIL_ENABLED"], "true")
        self.assertEqual(env["GOTRUE_MAILER_AUTOCONFIRM"], "false")
        self.assertEqual(env["GOTRUE_EXTERNAL_PHONE_ENABLED"], "false")
        self.assertEqual(env["GOTRUE_EXTERNAL_ANONYMOUS_USERS_ENABLED"], "false")
        self.assertEqual(env["GOTRUE_PASSWORD_MIN_LENGTH"], "10")  # SECURITY_NOTES 4.4
        self.assertEqual(env["GOTRUE_SECURITY_REFRESH_TOKEN_ROTATION_ENABLED"], "true")
        self.assertEqual(env["GOTRUE_JWT_AUD"], "authenticated")
        self.assertEqual(env["GOTRUE_JWT_ADMIN_ROLES"], "service_role")
        self.assertEqual(env["GOTRUE_SMTP_HOST"], "${SMTP_HOST}")
        for name in env:
            self.assertFalse(name.startswith("GOTRUE_MAILER_TEMPLATES_"), "e-mail templates arrive in phase 2 (C4)")

    def test_rest_exposes_public_schema_with_anon_role(self) -> None:
        env = environment_of(self.services["supabase-rest"])
        self.assertEqual(env["PGRST_DB_SCHEMAS"], "public")
        self.assertEqual(env["PGRST_DB_ANON_ROLE"], "anon")

    def test_storage_uses_the_file_backend_without_image_transformation(self) -> None:
        env = environment_of(self.services["supabase-storage"])
        self.assertEqual(env["STORAGE_BACKEND"], "file")
        self.assertEqual(env["FILE_STORAGE_BACKEND_PATH"], "/var/lib/storage")
        self.assertEqual(env["ENABLE_IMAGE_TRANSFORMATION"], "false")

    def test_kong_runs_dbless_with_the_planned_plugins_only(self) -> None:
        service = self.services["supabase-kong"]
        env = environment_of(service)
        self.assertEqual(env["KONG_DATABASE"], "off")
        self.assertEqual(env["KONG_DECLARATIVE_CONFIG"], "/home/kong/kong.yml")
        self.assertEqual(env["KONG_PLUGINS"], "cors,key-auth,acl,request-termination")
        self.assertIn("./kong.yml:/home/kong/temp.yml:ro", [str(v) for v in service["volumes"]])

    def test_studio_has_no_dashboard_credentials(self) -> None:
        self.assertNotIn("DASHBOARD_", self.text)

    def test_stack_secrets_use_the_mandatory_form(self) -> None:
        """A missing secret must fail loudly (`${VAR:?...}`), never silently become an empty value."""
        for ref in COMPOSE_REF.finditer(self.text):
            name, modifier = ref.group(1), ref.group(2) or ""
            if name in STACK_SECRETS:
                self.assertTrue(modifier.startswith(":?"), f"${{{name}}} must be written ${{{name}:?...}}")

    def test_every_interpolated_variable_without_default_is_in_the_stack_env_example(self) -> None:
        """Pitfall P6: the included file is interpolated from deploy/supabase/.env only."""
        self.assertTrue(ENV_EXAMPLE.is_file(), "deploy/supabase/.env.example is missing")
        defined = set(parse_env_file(ENV_EXAMPLE))
        for ref in COMPOSE_REF.finditer(self.text):
            name, modifier = ref.group(1), ref.group(2) or ""
            if not modifier.startswith(":-") and not modifier.startswith("-"):
                self.assertIn(name, defined, f"${{{name}}} is not defined in deploy/supabase/.env.example")


class RootComposeTest(unittest.TestCase):
    compose: dict[str, Any]
    services: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = load_yaml(ROOT_COMPOSE)
        cls.services = cls.compose["services"]

    def svc(self, name: str) -> dict[str, Any]:
        if name not in self.services:
            self.fail(f"service {name} is missing from docker-compose.yml")
        return self.services[name]

    def test_includes_the_supabase_stack_with_its_own_env_file(self) -> None:
        includes = self.compose.get("include")
        self.assertTrue(includes, "docker-compose.yml must `include` deploy/supabase/docker-compose.yml")
        entry = includes[0]
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["path"], "deploy/supabase/docker-compose.yml")
        env_files = entry["env_file"] if isinstance(entry["env_file"], list) else [entry["env_file"]]
        self.assertEqual(env_files, ["deploy/supabase/.env"])
        self.assertEqual(self.compose["name"], "soronua-predict")

    def test_mailpit(self) -> None:
        service = self.svc("mailpit")
        self.assertEqual(service["image"], MAILPIT_IMAGE)
        self.assertEqual(service["restart"], "unless-stopped")
        self.assertEqual(published(service), ["127.0.0.1:${MAILPIT_HOST_PORT:-54324}:8025"])  # SMTP 1025 stays internal
        self.assertIn("test", service["healthcheck"])

    def test_pgtap_service(self) -> None:
        service = self.svc("pgtap")
        self.assertEqual(service["image"], PGTAP_IMAGE)
        self.assertEqual(service["profiles"], ["tools"])
        self.assertEqual(service["working_dir"], "/tests")
        self.assertIn("./supabase/tests/database:/tests:ro", [str(v) for v in service["volumes"]])
        self.assertEqual(published(service), [])

    def test_toolbox_reaches_the_database_without_a_published_port(self) -> None:
        env = environment_of(self.svc("toolbox"))
        self.assertIn("DATABASE_URL", env)
        self.assertIn("@supabase-db:5432/", env["DATABASE_URL"])
        self.assertIn("${POSTGRES_PASSWORD", env["DATABASE_URL"])

    def test_api_receives_the_supabase_settings_by_allowlist(self) -> None:
        service = self.svc("api")
        self.assertNotIn("env_file", service)
        env = environment_of(service)
        self.assertEqual(env.get("SUPABASE_URL"), "${SUPABASE_URL:-http://supabase-kong:8000}")
        self.assertIn("SUPABASE_ANON_KEY", env)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", env)
        self.assertNotIn("supabase-db", str(service.get("depends_on", "")), "/api/health must stay up with the stack down")

    def test_web_and_e2e_never_receive_a_supabase_secret(self) -> None:
        for name in ("web", "e2e"):
            service = self.services[name]
            self.assertNotIn("env_file", service, name)
            for var, value in environment_of(service).items():
                self.assertIsNone(FORBIDDEN_WEB_NAME.search(var), f"{name}: {var} looks like a secret")
                self.assertNotIn("SERVICE_ROLE", value, f"{name}: {var} references the service role key")
                self.assertNotIn("${SUPABASE_", value, f"{name}: {var} would leak a Supabase variable (phase 2 only)")

    def test_web_does_not_depend_on_the_stack(self) -> None:
        depends = str(self.services["web"].get("depends_on", ""))
        self.assertNotIn("supabase", depends)

    def test_no_worker_yet(self) -> None:
        self.assertNotIn("worker", self.services)


if __name__ == "__main__":
    unittest.main()

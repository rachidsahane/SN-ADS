"""Unit tests for deploy/supabase/generate_keys.py (phase 1, spec 3.F). stdlib unittest, run in the toolbox.

Contract under test (spec 2.A.6):
- `python deploy/supabase/generate_keys.py --env local [--rotate]`
- reads `deploy/supabase/.env.example`, writes/completes `deploy/supabase/.env` (mode 600);
  a value that is absent, empty or `change-me` is generated, a real value is kept (idempotent);
  `--rotate` regenerates the secrets and re-signs ANON_KEY / SERVICE_ROLE_KEY;
- synchronises SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY and POSTGRES_PASSWORD into the ROOT `.env`
  (line by line, everything else preserved);
- never prints a value, only variable NAMES; `--env staging|production` fails ("phase 17").

The repository root is derived by the script from its own location (`<root>/deploy/supabase/`), so every test
copies the script into a throw-away tree: no real .env of the repository is ever read or modified.
Only dummy values are used; no secret lives in this file.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ._helpers import (
    ENV_EXAMPLE,
    EXAMPLE_VARIABLES,
    GENERATE_KEYS,
    REPO_ROOT,
    SECRET_VARIABLES,
    parse_env_file,
    parse_env_text,
)

ROOT_SYNCED = {
    "SUPABASE_ANON_KEY": "ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY": "SERVICE_ROLE_KEY",
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
}
FIVE_YEARS = 5 * 365 * 24 * 3600


def example_text() -> str:
    lines = ["# fixture mirroring deploy/supabase/.env.example (placeholders only)"]
    lines += [f"{key}={value}" for key, value in EXAMPLE_VARIABLES.items()]
    return "\n".join(lines) + "\n"


def b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


class KeyGeneratorCase(unittest.TestCase):
    """Base: a temporary repository tree holding a copy of the script and a fixture .env.example."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.stack = self.root / "deploy" / "supabase"
        self.stack.mkdir(parents=True)
        if not GENERATE_KEYS.is_file():
            self.fail("deploy/supabase/generate_keys.py is missing (phase 1 implementation not written yet)")
        shutil.copy(GENERATE_KEYS, self.stack / "generate_keys.py")
        (self.stack / ".env.example").write_text(example_text(), encoding="utf-8")
        self.deploy_env = self.stack / ".env"
        self.root_env = self.root / ".env"

    # -- helpers ---------------------------------------------------------------------------------------
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.stack / "generate_keys.py"), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def generate(self, *extra: str) -> subprocess.CompletedProcess[str]:
        result = self.run_script("--env", "local", *extra)
        self.assertEqual(result.returncode, 0, f"generate_keys failed (rc={result.returncode}): {result.stderr}")
        return result

    def values(self) -> dict[str, str]:
        self.assertTrue(self.deploy_env.is_file(), "deploy/supabase/.env was not written")
        return parse_env_file(self.deploy_env)

    def verify_jwt(self, token: str, secret: str) -> dict[str, object]:
        parts = token.split(".")
        self.assertEqual(len(parts), 3, "a JWT has three dot-separated segments")
        for part in parts:
            self.assertNotIn("=", part, "base64url without padding")
            self.assertRegex(part, r"^[A-Za-z0-9_-]+$")
        header = json.loads(b64url_decode(parts[0]))
        self.assertEqual(header.get("alg"), "HS256")
        self.assertEqual(header.get("typ"), "JWT")
        expected = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        self.assertTrue(hmac.compare_digest(expected, b64url_decode(parts[2])), "HMAC-SHA256 signature mismatch")
        payload: dict[str, object] = json.loads(b64url_decode(parts[1]))
        return payload


class GeneratedSecretsTest(KeyGeneratorCase):
    def test_anon_and_service_keys_are_valid_hs256_jwts_signed_with_jwt_secret(self) -> None:
        self.generate()
        values = self.values()
        anon = self.verify_jwt(values["ANON_KEY"], values["JWT_SECRET"])
        service = self.verify_jwt(values["SERVICE_ROLE_KEY"], values["JWT_SECRET"])
        self.assertEqual(anon["role"], "anon")
        self.assertEqual(service["role"], "service_role")
        for payload in (anon, service):
            self.assertEqual(payload["iss"], "supabase")
            self.assertIsInstance(payload["iat"], int)
            self.assertIsInstance(payload["exp"], int)
            self.assertGreater(payload["exp"], payload["iat"] + FIVE_YEARS)  # type: ignore[operator]
            self.assertLess(abs(payload["iat"] - time.time()), 24 * 3600)  # type: ignore[operator]
        self.assertNotEqual(values["ANON_KEY"], values["SERVICE_ROLE_KEY"])

    def test_keys_do_not_verify_with_another_secret(self) -> None:
        self.generate()
        values = self.values()
        with self.assertRaises(AssertionError):
            self.verify_jwt(values["ANON_KEY"], values["JWT_SECRET"] + "x")

    def test_secret_formats(self) -> None:
        self.generate()
        values = self.values()
        self.assertRegex(values["POSTGRES_PASSWORD"], r"^[A-Za-z0-9]{40}$")  # embedded in a URL: alphanumeric only
        self.assertRegex(values["JWT_SECRET"], r"^[A-Za-z0-9]{64,}$")
        self.assertEqual(len(values["PG_META_CRYPTO_KEY"]), 32)
        self.assertRegex(values["S3_PROTOCOL_ACCESS_KEY_ID"], r"^[0-9a-f]{32}$")
        self.assertRegex(values["S3_PROTOCOL_ACCESS_KEY_SECRET"], r"^[0-9a-f]{64}$")

    def test_all_secrets_are_distinct(self) -> None:
        self.generate()
        values = self.values()
        secrets = [values[name] for name in SECRET_VARIABLES]
        self.assertEqual(len(set(secrets)), len(secrets))

    def test_two_installations_get_different_secrets(self) -> None:
        self.generate()
        first = self.values()
        self.deploy_env.unlink()
        self.generate()
        second = self.values()
        for name in ("POSTGRES_PASSWORD", "JWT_SECRET", "PG_META_CRYPTO_KEY"):
            self.assertNotEqual(first[name], second[name], name)


class GeneratedEnvFileTest(KeyGeneratorCase):
    def test_env_contains_every_variable_of_the_example(self) -> None:
        self.generate()
        values = self.values()
        for name in EXAMPLE_VARIABLES:
            self.assertIn(name, values)

    def test_no_secret_is_left_as_placeholder_or_empty(self) -> None:
        self.generate()
        values = self.values()
        for name in SECRET_VARIABLES:
            self.assertNotIn(values[name], ("", "change-me"), name)

    def test_non_secret_values_are_copied_from_the_example(self) -> None:
        self.generate()
        values = self.values()
        for name, value in EXAMPLE_VARIABLES.items():
            if name not in SECRET_VARIABLES:
                self.assertEqual(values[name], value, name)

    def test_env_file_mode_is_600(self) -> None:
        self.generate()
        mode = stat.S_IMODE(os.stat(self.deploy_env).st_mode)
        self.assertEqual(mode, 0o600, oct(mode))

    def test_env_file_mode_is_600_even_when_the_file_pre_exists_with_looser_rights(self) -> None:
        self.deploy_env.write_text("POSTGRES_PASSWORD=change-me\n", encoding="utf-8")
        os.chmod(self.deploy_env, 0o644)
        self.generate()
        self.assertEqual(stat.S_IMODE(os.stat(self.deploy_env).st_mode), 0o600)

    def test_a_missing_variable_is_added_from_the_example(self) -> None:
        self.deploy_env.write_text("POSTGRES_PASSWORD=change-me\n", encoding="utf-8")
        self.generate()
        values = self.values()
        self.assertEqual(values["SITE_URL"], "http://localhost:3000")
        self.assertEqual(len(values["POSTGRES_PASSWORD"]), 40)


class IdempotenceTest(KeyGeneratorCase):
    def test_second_run_leaves_both_files_byte_identical(self) -> None:
        self.root_env.write_text("# local\nWEB_HOST_PORT=3000\n", encoding="utf-8")
        self.generate()
        deploy_first = self.deploy_env.read_bytes()
        root_first = self.root_env.read_bytes()
        self.generate()
        self.assertEqual(self.deploy_env.read_bytes(), deploy_first)
        self.assertEqual(self.root_env.read_bytes(), root_first)

    def test_real_values_already_present_are_kept(self) -> None:
        kept_password = "P" * 40
        kept_url = "http://localhost:4000"
        self.deploy_env.write_text(
            f"POSTGRES_PASSWORD={kept_password}\nSITE_URL={kept_url}\nANON_KEY=change-me\nJWT_SECRET=\n",
            encoding="utf-8",
        )
        self.generate()
        values = self.values()
        self.assertEqual(values["POSTGRES_PASSWORD"], kept_password)
        self.assertEqual(values["SITE_URL"], kept_url)
        # only the placeholder / empty ones were generated
        self.assertNotIn(values["ANON_KEY"], ("", "change-me"))
        self.assertRegex(values["JWT_SECRET"], r"^[A-Za-z0-9]{64,}$")
        self.verify_jwt(values["ANON_KEY"], values["JWT_SECRET"])

    def test_a_kept_jwt_secret_signs_the_generated_keys(self) -> None:
        kept_secret = "S" * 64
        self.deploy_env.write_text(f"JWT_SECRET={kept_secret}\n", encoding="utf-8")
        self.generate()
        values = self.values()
        self.assertEqual(values["JWT_SECRET"], kept_secret)
        self.verify_jwt(values["ANON_KEY"], kept_secret)
        self.verify_jwt(values["SERVICE_ROLE_KEY"], kept_secret)


class RotateTest(KeyGeneratorCase):
    def test_rotate_regenerates_secrets_and_resigns_both_keys(self) -> None:
        self.generate()
        before = self.values()
        self.generate("--rotate")
        after = self.values()
        for name in ("POSTGRES_PASSWORD", "JWT_SECRET", "ANON_KEY", "SERVICE_ROLE_KEY", "PG_META_CRYPTO_KEY"):
            self.assertNotEqual(before[name], after[name], name)
        self.verify_jwt(after["ANON_KEY"], after["JWT_SECRET"])
        self.verify_jwt(after["SERVICE_ROLE_KEY"], after["JWT_SECRET"])
        with self.assertRaises(AssertionError):  # the old keys no longer verify with the new secret
            self.verify_jwt(before["ANON_KEY"], after["JWT_SECRET"])

    def test_rotate_keeps_non_secret_values(self) -> None:
        self.generate()
        self.deploy_env.write_text(
            self.deploy_env.read_text(encoding="utf-8").replace(
                "SITE_URL=http://localhost:3000", "SITE_URL=http://localhost:4000"
            ),
            encoding="utf-8",
        )
        self.generate("--rotate")
        self.assertEqual(self.values()["SITE_URL"], "http://localhost:4000")

    def test_rotate_updates_the_root_env(self) -> None:
        self.generate()
        self.generate("--rotate")
        values = self.values()
        root = parse_env_file(self.root_env)
        for root_name, deploy_name in ROOT_SYNCED.items():
            self.assertEqual(root[root_name], values[deploy_name], root_name)


class RootEnvSyncTest(KeyGeneratorCase):
    ORIGINAL = (
        "# Soro Nua Campaign Predictor - LOCAL environment\n"
        "WEB_HOST_PORT=3000\n"
        "\n"
        "# api\n"
        "APP_ENV=local\n"
        "LOG_LEVEL=DEBUG\n"
    )

    def test_missing_lines_are_appended_and_the_rest_is_preserved(self) -> None:
        self.root_env.write_text(self.ORIGINAL, encoding="utf-8")
        self.generate()
        text = self.root_env.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(self.ORIGINAL), "existing lines, comments and order must be preserved")
        values = self.values()
        root = parse_env_text(text)
        for root_name, deploy_name in ROOT_SYNCED.items():
            self.assertEqual(root[root_name], values[deploy_name], root_name)
        for name in ROOT_SYNCED:
            self.assertEqual(text.count(f"{name}="), 1, f"{name} must appear exactly once")

    def test_existing_lines_are_updated_in_place(self) -> None:
        original = (
            "# header\n"
            "SUPABASE_ANON_KEY=change-me\n"
            "WEB_HOST_PORT=3000\n"
            "POSTGRES_PASSWORD=change-me\n"
            "# footer\n"
            "SUPABASE_SERVICE_ROLE_KEY=\n"
        )
        self.root_env.write_text(original, encoding="utf-8")
        self.generate()
        lines = self.root_env.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# header")
        self.assertTrue(lines[1].startswith("SUPABASE_ANON_KEY=") and lines[1] != "SUPABASE_ANON_KEY=change-me")
        self.assertEqual(lines[2], "WEB_HOST_PORT=3000")
        self.assertTrue(lines[3].startswith("POSTGRES_PASSWORD=") and lines[3] != "POSTGRES_PASSWORD=change-me")
        self.assertEqual(lines[4], "# footer")
        self.assertTrue(lines[5].startswith("SUPABASE_SERVICE_ROLE_KEY=") and len(lines[5]) > len("SUPABASE_SERVICE_ROLE_KEY="))
        values = self.values()
        root = parse_env_text("\n".join(lines))
        for root_name, deploy_name in ROOT_SYNCED.items():
            self.assertEqual(root[root_name], values[deploy_name], root_name)

    def test_root_env_without_trailing_newline_is_not_corrupted(self) -> None:
        self.root_env.write_text("WEB_HOST_PORT=3000", encoding="utf-8")  # no final newline
        self.generate()
        root = parse_env_file(self.root_env)
        self.assertEqual(root["WEB_HOST_PORT"], "3000")
        self.assertIn("SUPABASE_ANON_KEY", root)

    def test_unrelated_root_variables_are_never_touched(self) -> None:
        self.root_env.write_text(self.ORIGINAL + "SUPABASE_URL=http://supabase-kong:8000\n", encoding="utf-8")
        self.generate()
        root = parse_env_file(self.root_env)
        self.assertEqual(root["SUPABASE_URL"], "http://supabase-kong:8000")
        self.assertEqual(root["LOG_LEVEL"], "DEBUG")


class OutputNeverLeaksSecretsTest(KeyGeneratorCase):
    def _assert_no_value_printed(self, result: subprocess.CompletedProcess[str]) -> None:
        output = result.stdout + result.stderr
        values = self.values()
        for name in SECRET_VARIABLES:
            self.assertNotIn(values[name], output, f"the value of {name} was printed")
        root = parse_env_file(self.root_env) if self.root_env.exists() else {}
        for name, value in root.items():
            if name in ROOT_SYNCED:
                self.assertNotIn(value, output, f"the value of {name} was printed")
        for segment in values["ANON_KEY"].split("."):
            self.assertNotIn(segment, output)

    def test_first_run_prints_names_but_no_value(self) -> None:
        result = self.generate()
        output = result.stdout + result.stderr
        for name in ("POSTGRES_PASSWORD", "JWT_SECRET", "ANON_KEY", "SERVICE_ROLE_KEY"):
            self.assertIn(name, output)
        self._assert_no_value_printed(result)

    def test_second_run_and_rotate_print_no_value(self) -> None:
        self.generate()
        self._assert_no_value_printed(self.generate())
        self._assert_no_value_printed(self.generate("--rotate"))


class AwsModesAreRefusedTest(KeyGeneratorCase):
    def test_staging_and_production_fail_with_a_phase_17_message_and_write_nothing(self) -> None:
        self.root_env.write_text("WEB_HOST_PORT=3000\n", encoding="utf-8")
        before = self.root_env.read_bytes()
        for target in ("staging", "production"):
            with self.subTest(env=target):
                result = self.run_script("--env", target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("phase 17", (result.stdout + result.stderr).lower())
                self.assertFalse(self.deploy_env.exists(), "no file may be written")
                self.assertEqual(self.root_env.read_bytes(), before)

    def test_an_unknown_env_is_rejected(self) -> None:
        result = self.run_script("--env", "nonsense")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.deploy_env.exists())


class RepositoryFilesTest(unittest.TestCase):
    """Static checks on the committed files (no secret committed, standard library only)."""

    def test_generate_keys_script_exists(self) -> None:
        self.assertTrue(GENERATE_KEYS.is_file(), "deploy/supabase/generate_keys.py is missing")

    def test_generate_keys_uses_the_standard_library_only(self) -> None:
        if not GENERATE_KEYS.is_file():
            self.fail("deploy/supabase/generate_keys.py is missing")
        tree = ast.parse(GENERATE_KEYS.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, set(sys.stdlib_module_names) | {"__future__"}, sorted(imported))

    def test_env_example_lists_every_variable_with_placeholders_only(self) -> None:
        self.assertTrue(ENV_EXAMPLE.is_file(), "deploy/supabase/.env.example is missing")
        values = parse_env_file(ENV_EXAMPLE)
        for name, expected in EXAMPLE_VARIABLES.items():
            self.assertIn(name, values, f"{name} missing from .env.example")
            self.assertEqual(values[name], expected, name)

    def test_env_example_has_no_out_of_scope_variable_and_no_real_secret(self) -> None:
        self.assertTrue(ENV_EXAMPLE.is_file(), "deploy/supabase/.env.example is missing")
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        for forbidden in ("DASHBOARD_", "BACKUP_", "GOTRUE_MAILER_TEMPLATES_"):
            self.assertNotIn(forbidden, text, f"{forbidden}* is out of phase 1 scope (spec C4, C6)")
        self.assertNotRegex(text, r"eyJ[A-Za-z0-9_-]{10,}", "a JWT must never be committed")

    def test_the_real_env_file_is_git_ignored(self) -> None:
        ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("deploy/supabase/.env", [line.strip() for line in ignored])


if __name__ == "__main__":
    unittest.main()

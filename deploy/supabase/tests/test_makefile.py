"""Static checks of the Makefile wiring required by phase 1 (spec 2.D, pitfalls P5, P11, P16, P19).

The Makefile is read as text (no `make` run, no Docker): these tests only pin what the spec makes
mandatory, so a refactoring of the recipes stays free as long as the contract holds.
"""

from __future__ import annotations

import re
import unittest

from ._helpers import REPO_ROOT

MAKEFILE = REPO_ROOT / "Makefile"
NEW_PHONY_TARGETS = ("db-reset", "db-migrate", "db-new-migration", "db-shell", "pull")
VOLUMES = ("supabase-db-data", "supabase-db-config", "supabase-storage-data")


def read() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def phony_block(text: str) -> str:
    """The .PHONY declaration with its backslash continuations."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(".PHONY:"))
    block = [lines[start]]
    while block[-1].rstrip().endswith("\\"):
        start += 1
        block.append(lines[start])
    return " ".join(block)


def target_block(text: str, name: str) -> tuple[str, str]:
    """(prerequisite line, recipe text) of a target; fails the test when the target does not exist."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(name)}:(?!=)(.*)$", line)
        if match:
            recipe: list[str] = []
            for follower in lines[index + 1 :]:
                if follower.startswith("\t") or follower.strip() == "" or follower.startswith("#"):
                    recipe.append(follower)
                else:
                    break
            return match.group(1), "\n".join(recipe)
    raise AssertionError(f"Makefile target {name} is missing (phase 1 implementation not written yet)")


class MakefileTargetsTest(unittest.TestCase):
    text: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read()

    def test_new_targets_are_declared_phony_and_documented(self) -> None:
        phony = phony_block(self.text)
        for name in NEW_PHONY_TARGETS:
            self.assertRegex(phony, rf"\b{name}\b", f"{name} must be in .PHONY")
            header, _ = target_block(self.text, name)
            self.assertIn("##", header, f"{name} needs a help comment (## ...)")

    def test_profiles_include_local_so_meta_and_studio_are_cleaned_and_built(self) -> None:
        match = re.search(r"^PROFILES\s*:=(.*)$", self.text, flags=re.M)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("--profile local", match.group(1))

    def test_no_prune_anywhere(self) -> None:
        """The machine hosts other projects: no global clean-up command may exist (P16)."""
        code = "\n".join(line for line in self.text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("prune", code)

    def test_volume_removal_is_only_done_with_a_down_in_clean_or_by_project_label(self) -> None:
        for line in self.text.splitlines():
            if "docker volume rm" in line:
                self.assertIn("com.docker.compose.project=soronua-predict", self.text)
            if re.search(r"\bdown\b.*\s-v\b|\bdown\s+-v\b", line):
                _, clean = target_block(self.text, "clean")
                self.assertIn(line.strip(), clean, "`down -v` is only allowed in the clean target")

    def test_commands_that_call_compose_first_make_sure_the_stack_env_file_exists(self) -> None:
        """P5: `include` fails without deploy/supabase/.env, so env-local must run first."""
        for name in ("build", "up", "up-fresh", "lint", "pre-commit"):
            header, recipe = target_block(self.text, name)
            self.assertTrue(
                "env-local" in header or re.search(r"\$\(MAKE\)[^\n]*\benv-local\b", recipe.split("\n")[0]),
                f"{name} must depend on env-local",
            )

    def test_env_local_prepares_the_stack_env_file_then_generates_keys(self) -> None:
        _, recipe = target_block(self.text, "env-local")
        self.assertIn("deploy/supabase/.env.example", recipe)
        self.assertIn("deploy/supabase/.env", recipe)
        copy_at = recipe.index("cp deploy/supabase/.env.example deploy/supabase/.env")
        generate_at = recipe.index("generate_keys.py")
        self.assertLess(copy_at, generate_at, "the placeholder file must exist before the toolbox can start")
        self.assertIn("--env local", recipe)

    def test_pull_target_fetches_the_images_that_are_not_built(self) -> None:
        _, recipe = target_block(self.text, "pull")
        self.assertIn("pull", recipe)
        self.assertIn("--ignore-buildable", recipe)
        _, build = target_block(self.text, "build")
        self.assertIn("pull", build)


class DatabaseTargetsTest(unittest.TestCase):
    text: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read()

    def test_db_migrate_uses_the_database_url_from_the_environment(self) -> None:
        _, recipe = target_block(self.text, "db-migrate")
        self.assertIn("supabase migration up", recipe)
        self.assertIn('--db-url "$$DATABASE_URL"', recipe)
        self.assertNotRegex(recipe, r"postgres(ql)?://\S+:\S+@", "no password may appear in the command line")

    def test_db_new_migration_requires_a_name(self) -> None:
        _, recipe = target_block(self.text, "db-new-migration")
        self.assertIn("name=", recipe)
        self.assertIn("exit 1", recipe)
        self.assertIn("supabase migration new", recipe)

    def test_db_shell_opens_psql_without_any_published_port(self) -> None:
        _, recipe = target_block(self.text, "db-shell")
        self.assertIn("psql", recipe)
        self.assertIn("supabase-db", recipe)
        self.assertNotIn("localhost", recipe)

    def test_db_reset_recreates_the_database_volumes_of_this_project_only_then_migrates(self) -> None:
        _, recipe = target_block(self.text, "db-reset")
        self.assertIn("com.docker.compose.project=soronua-predict", recipe)
        for volume in VOLUMES:
            self.assertIn(volume, recipe, f"db-reset must remove {volume} (orphan storage files otherwise, P11)")
        self.assertIn("db-migrate", recipe)
        self.assertLess(recipe.index("volume rm"), recipe.index("db-migrate"))
        self.assertIn("--wait", recipe, "wait for gotrue/storage to finish their own migrations (P10)")
        for service in ("supabase-db", "supabase-auth", "supabase-rest", "supabase-storage", "supabase-kong"):
            self.assertIn(service, recipe)
        self.assertNotIn("down -v", recipe, "db-reset must not stop the whole project")

    def test_up_starts_the_whole_stack_and_applies_the_migrations(self) -> None:
        for name in ("up", "up-fresh"):
            _, recipe = target_block(self.text, name)
            self.assertIn("--profile local", recipe, name)
            self.assertIn("--wait", recipe, name)
            self.assertIn("db-migrate", recipe, name)
            self.assertNotRegex(recipe, r"up -d[^\n]*\bredis api web\b", f"{name}: no explicit service list any more")

    def test_down_also_stops_meta_and_studio(self) -> None:
        _, recipe = target_block(self.text, "down")
        self.assertIn("--profile local", recipe)

    def test_test_db_is_real_and_runs_pg_prove_through_the_pgtap_service(self) -> None:
        _, recipe = target_block(self.text, "test-db")
        self.assertNotIn("SKIP", recipe, "the phase 0 placeholder guard must be gone")
        self.assertIn("db-migrate", recipe)
        self.assertIn("create extension if not exists pgtap", recipe)
        self.assertIn("pgtap", recipe)
        self.assertIn("supabase-db", recipe)
        self.assertLess(recipe.index("db-migrate"), recipe.index("create extension"))

    def test_pgtap_is_never_installed_by_a_migration_target(self) -> None:
        for name in ("db-migrate", "db-reset", "up"):
            _, recipe = target_block(self.text, name)
            self.assertNotIn("pgtap", recipe.lower(), f"{name} must not install pgTAP")

    def test_unit_tests_include_the_stack_tests_and_guards_include_the_compose_guards(self) -> None:
        _, unit = target_block(self.text, "test-unit")
        self.assertIn("unittest discover -s deploy/supabase/tests", unit)
        _, guards = target_block(self.text, "guards")
        self.assertIn("compose_guards.py", guards)
        self.assertIn("config --format json", guards)
        self.assertNotRegex(guards, r"config\s*(>|$)", "the resolved configuration holds secrets: pipe it, never print it")


if __name__ == "__main__":
    unittest.main()

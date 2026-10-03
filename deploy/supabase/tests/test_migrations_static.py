"""Static rules every migration of every phase must follow (CLAUDE 3.5 and 4.4, DATA_MODEL 6 and 7, SECURITY_NOTES 3.7).

Behaviour is proven by the pgTAP files in supabase/tests/database; these checks only read the SQL text, so a
rule broken in a later phase is caught even before a database is involved. Generic on purpose: they grow with
the migrations and never need to be edited when a phase adds a table.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from ._helpers import REPO_ROOT

MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
NAME = re.compile(r"^(\d{14})_([a-z0-9_]+)\.sql$")


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def migrations() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"))


def statements(sql: str) -> list[str]:
    """Statements split on `;` outside dollar-quoted bodies (enough for our migrations)."""
    out: list[str] = []
    buffer: list[str] = []
    in_dollar = False
    for line in strip_comments(sql).splitlines():
        buffer.append(line)
        in_dollar ^= line.count("$$") % 2 == 1
        if not in_dollar and line.rstrip().endswith(";"):
            out.append("\n".join(buffer).strip())
            buffer = []
    if "".join(buffer).strip():
        out.append("\n".join(buffer).strip())
    return out


class MigrationFilesTest(unittest.TestCase):
    def test_phase_1_migrations_exist_in_order(self) -> None:
        names = [p.name for p in migrations()]
        self.assertTrue(names, "supabase/migrations is empty (phase 1 implementation not written yet)")
        by_suffix = {NAME.match(n).group(2): NAME.match(n).group(1) for n in names if NAME.match(n)}  # type: ignore[union-attr]
        self.assertIn("init_enums_profiles", by_suffix)
        self.assertIn("audit_log", by_suffix)
        self.assertLess(by_suffix["init_enums_profiles"], by_suffix["audit_log"])

    def test_names_are_timestamped_snake_case_and_unique(self) -> None:
        names = [p.name for p in migrations()]
        self.assertTrue(names, "supabase/migrations is empty (phase 1 implementation not written yet)")
        stamps = []
        for name in names:
            match = NAME.match(name)
            self.assertIsNotNone(match, f"{name}: expected <14-digit timestamp>_<snake_case>.sql")
            stamps.append(match.group(1))  # type: ignore[union-attr]
        self.assertEqual(len(stamps), len(set(stamps)), "two migrations share a version")
        self.assertEqual(stamps, sorted(stamps))


class MigrationRulesTest(unittest.TestCase):
    sql: dict[str, str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = {p.name: strip_comments(p.read_text(encoding="utf-8")) for p in migrations()}

    def test_there_is_something_to_check(self) -> None:
        self.assertTrue(self.sql, "supabase/migrations is empty (phase 1 implementation not written yet)")

    def test_every_new_table_has_rls_enabled_and_forced_in_the_same_migration(self) -> None:
        tables = 0
        for name, text in self.sql.items():
            for match in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?public\.(\w+)", text, flags=re.I):
                tables += 1
                table = match.group(1)
                self.assertRegex(text, rf"alter\s+table\s+public\.{table}\s+enable\s+row\s+level\s+security", f"{name}: {table}")
                self.assertRegex(text, rf"alter\s+table\s+public\.{table}\s+force\s+row\s+level\s+security", f"{name}: {table}")
        if self.sql:
            self.assertGreaterEqual(tables, 1, "no `create table public.*` found: the rule was not exercised")

    def test_rls_is_never_weakened(self) -> None:
        for name, text in self.sql.items():
            self.assertNotRegex(text, r"disable\s+row\s+level\s+security", name)
            self.assertNotRegex(text, r"no\s+force\s+row\s+level\s+security", name)
            self.assertNotRegex(text, r"\bbypassrls\b", name)

    def test_pgtap_is_never_created_by_a_migration(self) -> None:
        for name, text in self.sql.items():
            self.assertNotRegex(text, r"create\s+extension[^;]*pgtap", f"{name}: pgTAP is local-only (P4)")

    def test_every_security_definer_function_pins_an_empty_search_path(self) -> None:
        definers = 0
        for name, text in self.sql.items():
            for chunk in re.split(r"(?=create\s+(?:or\s+replace\s+)?function\b)", text, flags=re.I)[1:]:
                header = chunk.split("$$", 1)[0]
                if re.search(r"security\s+definer", header, flags=re.I):
                    definers += 1
                    self.assertRegex(header, r"set\s+search_path\s*=\s*''", f"{name}: {header.split('(')[0].strip()}")
        if self.sql:
            self.assertGreaterEqual(definers, 1, "no security definer function found: the rule was not exercised")

    def test_every_function_is_revoked_from_public_then_granted_explicitly(self) -> None:
        """Postgres grants EXECUTE to PUBLIC by default; an API-callable function must opt in (SECURITY_NOTES 3.7)."""
        for name, text in self.sql.items():
            created = set(re.findall(r"create\s+(?:or\s+replace\s+)?function\s+public\.(\w+)\s*\(", text, flags=re.I))
            for function in created:
                self.assertRegex(
                    text,
                    rf"revoke\s+all\s+on\s+function\s+public\.{function}\s*\([^)]*\)\s+from\s+[^;]*\bpublic\b",
                    f"{name}: public.{function}() must be revoked from PUBLIC",
                )

    def test_anon_is_granted_nothing_except_the_readiness_function(self) -> None:
        for name, text in self.sql.items():
            for statement in statements(text):
                if re.match(r"grant\b", statement, flags=re.I) and re.search(r"\banon\b", statement, flags=re.I):
                    self.assertRegex(statement, r"public\.schema_version\(\)", f"{name}: {statement[:80]!r}")

    def test_no_secret_or_literal_password_in_a_migration(self) -> None:
        for name, text in self.sql.items():
            self.assertNotRegex(text, r"(?i)\bpassword\s*(=|')", name)
            self.assertNotRegex(text, r"eyJ[A-Za-z0-9_-]{10,}", name)

    def test_default_privileges_are_hardened_for_anon_in_the_first_migration(self) -> None:
        first = [text for name, text in self.sql.items() if name.endswith("_init_enums_profiles.sql")]
        self.assertTrue(first, "first phase 1 migration is missing")
        text = first[0]
        for kind in ("tables", "sequences", "functions"):
            self.assertRegex(
                text,
                rf"alter\s+default\s+privileges[^;]*revoke[^;]*on\s+{kind}\s+from\s+[^;]*\banon\b",
                f"default privileges on {kind} must be revoked from anon (spec C12, pitfall P2)",
            )

    def test_functions_created_later_are_closed_to_public_by_default(self) -> None:
        """has_function_privilege('anon', ...) is also true through PUBLIC: the global default must be revoked.

        `alter default privileges IN SCHEMA ... revoke ... from anon` cannot remove PUBLIC's built-in EXECUTE
        (PostgreSQL documents that a globally granted privilege is only revoked by the global form), and
        pgTAP test 090 (c) fails for a function created after the migration. Hence this guard.
        """
        first = [text for name, text in self.sql.items() if name.endswith("_init_enums_profiles.sql")]
        self.assertTrue(first, "first phase 1 migration is missing")
        self.assertRegex(
            first[0],
            r"alter\s+default\s+privileges\s+(?:for\s+role\s+\w+\s+)?revoke\s+execute\s+on\s+functions\s+from\s+public",
            "a global `alter default privileges ... revoke execute on functions from public` is required",
        )


if __name__ == "__main__":
    unittest.main()

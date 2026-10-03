"""deploy/supabase/db/roles.sql and jwt.sql: the init scripts mounted in supabase-db (spec 2.A.4 and 2.A.5).

Static checks only. The point is that the internal role passwords follow POSTGRES_PASSWORD (read from the
container environment, never written in the file) and that nothing else is configured by these scripts.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from ._helpers import REPO_ROOT, STACK_DIR

ROLES = STACK_DIR / "db" / "roles.sql"
JWT = STACK_DIR / "db" / "jwt.sql"
INTERNAL_ROLES = ("authenticator", "supabase_auth_admin", "supabase_storage_admin")


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} is missing (phase 1 implementation not written yet)")
    return path.read_text(encoding="utf-8")


class RolesScriptTest(unittest.TestCase):
    def test_the_password_comes_from_the_container_environment(self) -> None:
        text = read(ROLES)
        self.assertRegex(text, r"\\set\s+pgpass\s+`echo\s+\"\$POSTGRES_PASSWORD\"`")

    def test_each_internal_role_follows_that_password_through_a_psql_variable(self) -> None:
        text = read(ROLES)
        for role in INTERNAL_ROLES:
            self.assertRegex(text, rf"ALTER\s+USER\s+{role}\s+WITH\s+PASSWORD\s+:'pgpass'\s*;", role)

    def test_no_literal_password_and_no_other_statement(self) -> None:
        text = re.sub(r"--[^\n]*", "", read(ROLES))
        self.assertNotRegex(text, r"PASSWORD\s+'", "a literal password must never be written in the script")
        statements = [s.strip() for s in text.replace("\\set pgpass `echo \"$POSTGRES_PASSWORD\"`", "").split(";") if s.strip()]
        self.assertTrue(statements)
        for statement in statements:
            self.assertRegex(statement, r"^ALTER\s+USER\s+\w+\s+WITH\s+PASSWORD\s+:'pgpass'$", statement)


class JwtScriptTest(unittest.TestCase):
    def test_the_token_lifetime_is_stored_as_a_database_setting(self) -> None:
        text = read(JWT)
        self.assertRegex(text, r"\\set\s+jwt_exp\s+`echo\s+\"\$JWT_EXP\"`")
        self.assertRegex(text, r"ALTER\s+DATABASE\s+postgres\s+SET\s+\"app\.settings\.jwt_exp\"\s+TO\s+:'jwt_exp'\s*;")

    def test_it_contains_no_secret(self) -> None:
        text = read(JWT)
        self.assertNotRegex(text, r"eyJ[A-Za-z0-9_-]{10,}")
        self.assertNotIn("JWT_SECRET", text)


if __name__ == "__main__":
    unittest.main()

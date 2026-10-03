"""Static checks of the invite and recovery e-mail templates served by `web` (phase 2, spec 2.C, D-053, D-068).

gotrue fetches `GOTRUE_MAILER_TEMPLATES_INVITE` / `_RECOVERY` over HTTP from web at send time and renders them with
Go templates. The link must go to `/auth/confirm` with the hashed token (no PKCE, works from any browser), built from
`{{ .SiteURL }}` and never from `{{ .RedirectTo }}` (it falls back to the site root and would break the recovery URL).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from ._helpers import REPO_ROOT

TEMPLATE_DIR = REPO_ROOT / "apps" / "web" / "public" / "auth-templates"
PRETTIERIGNORE = REPO_ROOT / "apps" / "web" / ".prettierignore"

# kind -> (exact link as written in the HTML source, heading, link text, intro sentence, closing sentence)
EXPECTED: dict[str, dict[str, str]] = {
    "invite": {
        "url": "{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&amp;type=invite&amp;next=/auth/set-password",
        "heading": "You have been invited",
        "intro": "You have been invited to Soro Nua Campaign Predictor, the internal tool of Soro Nua Agency.",
        "link_text": "Set your password",
        "closing": "This link can be used once. If you were not expecting this invitation, you can ignore this e-mail.",
    },
    "recovery": {
        "url": "{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&amp;type=recovery&amp;next=/auth/set-password",
        "heading": "Reset your password",
        "intro": "We received a request to reset your Soro Nua Campaign Predictor password.",
        "link_text": "Set a new password",
        "closing": "If you did not ask for this, you can ignore this e-mail.",
    },
}
ALLOWED_GO_VARIABLES = {".SiteURL", ".TokenHash", ".Email"}


def read_template(kind: str) -> str:
    path = TEMPLATE_DIR / f"{kind}.html"
    if not path.is_file():
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} is missing (phase 2 implementation not written yet)")
    return path.read_text(encoding="utf-8")


class AuthTemplatesTest(unittest.TestCase):
    def test_both_templates_exist_and_the_placeholder_file_is_gone(self) -> None:
        for kind in EXPECTED:
            read_template(kind)
        self.assertFalse((TEMPLATE_DIR / ".gitkeep").exists(), "the .gitkeep placeholder must be removed")

    def test_templates_are_complete_self_contained_html_documents(self) -> None:
        for kind in EXPECTED:
            text = read_template(kind)
            self.assertRegex(text.lstrip().lower(), r"^<!doctype html>", kind)
            self.assertIn('<meta charset="utf-8"', text.lower(), kind)
            self.assertIn("<title>", text.lower(), kind)
            self.assertRegex(text, r'<html[^>]*\blang="en"', f"{kind}: interface language is English")

    def test_link_goes_to_auth_confirm_with_the_hashed_token_and_the_site_url(self) -> None:
        for kind, expected in EXPECTED.items():
            text = read_template(kind)
            href = re.search(r'href="([^"]*auth/confirm[^"]*)"', text)
            self.assertIsNotNone(href, f"{kind}: no link to /auth/confirm")
            assert href is not None
            self.assertEqual(href.group(1), expected["url"], kind)

    def test_link_url_is_also_repeated_as_plain_text_for_clients_that_strip_links(self) -> None:
        for kind, expected in EXPECTED.items():
            text = read_template(kind)
            self.assertGreaterEqual(text.count(expected["url"]), 2, f"{kind}: URL must appear in the href and as text")

    def test_only_known_go_template_variables_and_never_redirect_to(self) -> None:
        for kind in EXPECTED:
            text = read_template(kind)
            variables = set(re.findall(r"\{\{\s*(\.\w+)\s*\}\}", text))
            self.assertTrue(variables <= ALLOWED_GO_VARIABLES, f"{kind}: unexpected variables {variables - ALLOWED_GO_VARIABLES}")
            self.assertIn(".SiteURL", variables, kind)
            self.assertIn(".TokenHash", variables, kind)
            self.assertNotIn(".RedirectTo", text, f"{kind}: use .SiteURL (RedirectTo falls back to the site root)")
            self.assertNotIn(".ConfirmationURL", text, f"{kind}: the link must use token_hash, not the gotrue verify URL")
            self.assertEqual(text.count("{{"), text.count("}}"), f"{kind}: unbalanced template braces")

    def test_english_wording(self) -> None:
        for kind, expected in EXPECTED.items():
            text = read_template(kind)
            for key in ("heading", "intro", "link_text", "closing"):
                self.assertIn(expected[key], text, f"{kind}: missing text {expected[key]!r}")

    def test_the_two_templates_use_different_types(self) -> None:
        self.assertIn("type=invite", read_template("invite"))
        self.assertNotIn("type=recovery", read_template("invite"))
        self.assertIn("type=recovery", read_template("recovery"))
        self.assertNotIn("type=invite", read_template("recovery"))

    def test_no_remote_resource_script_or_tracking(self) -> None:
        for kind in EXPECTED:
            text = read_template(kind).lower()
            self.assertNotIn("<script", text, kind)
            self.assertNotIn("<img", text, f"{kind}: no remote image / tracking pixel")
            self.assertNotIn("<iframe", text, kind)
            self.assertNotRegex(text, r'<link[^>]+rel="?stylesheet', f"{kind}: inline CSS only")
            self.assertNotRegex(text, r"url\(\s*['\"]?https?:", f"{kind}: no remote CSS resource")
            self.assertNotRegex(text, r'\bsrc="', kind)
            # The only absolute URL allowed is the one built from the template variables.
            self.assertNotRegex(text, r'https?://', f"{kind}: no hard-coded absolute URL (use {{{{ .SiteURL }}}})")

    def test_no_secret_shaped_content(self) -> None:
        for kind in EXPECTED:
            self.assertNotRegex(read_template(kind), r"eyJ[A-Za-z0-9_-]{10,}", kind)

    def test_prettier_ignores_the_templates_because_go_braces_break_it(self) -> None:
        self.assertTrue(PRETTIERIGNORE.is_file(), "apps/web/.prettierignore is missing")
        lines = [line.strip() for line in PRETTIERIGNORE.read_text(encoding="utf-8").splitlines()]
        self.assertIn("public/auth-templates/", lines)


class TemplateLocationTest(unittest.TestCase):
    def test_default_stack_env_points_to_files_that_exist_in_web_public(self) -> None:
        """The URL path of each template maps 1:1 to a file served from apps/web/public."""
        from ._helpers import ENV_EXAMPLE, parse_env_file

        values = parse_env_file(ENV_EXAMPLE)
        for kind, variable in (("invite", "GOTRUE_MAILER_TEMPLATES_INVITE"), ("recovery", "GOTRUE_MAILER_TEMPLATES_RECOVERY")):
            url = values.get(variable, "")
            match = re.fullmatch(r"http://web:3000/(auth-templates/[a-z]+\.html)", url)
            self.assertIsNotNone(match, f"{variable} must be http://web:3000/auth-templates/{kind}.html (got {url!r})")
            assert match is not None
            self.assertEqual(match.group(1), f"auth-templates/{kind}.html")
            self.assertTrue(Path(REPO_ROOT / "apps" / "web" / "public" / match.group(1)).is_file())


if __name__ == "__main__":
    unittest.main()

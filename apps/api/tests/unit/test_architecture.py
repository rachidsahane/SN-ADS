"""Guards from docs/TESTING.md section 2 that already make sense in phase 0."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN_IN_DOMAIN = ("supabase", "redis", "httpx", "app.infra")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_environment_reads_outside_config() -> None:
    offenders = []
    scanned = list(APP.rglob("*.py"))
    assert scanned, "the guard scanned no file: APP path is wrong"
    for path in scanned:
        if path.name == "config.py" and path.parent == APP:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            is_os_environ = isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}
            is_env_import = (
                isinstance(node, ast.ImportFrom)
                and node.module == "os"
                and any(alias.name in {"environ", "getenv"} for alias in node.names)
            )
            if is_os_environ or is_env_import:
                offenders.append(str(path.relative_to(APP)))
    assert offenders == []


def test_domain_has_no_io_imports() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in (APP / "domain").rglob("*.py")
        for name in _imports(path)
        if name.split(".")[0] in {"supabase", "redis", "httpx"} or name.startswith("app.infra")
    ]
    assert offenders == []

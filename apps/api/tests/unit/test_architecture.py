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


# --- Phase 1: the service-role client has a closed list of consumers (TESTING 2, ARCHITECTURE 2.5,
# CLAUDE 4.2) ---

SERVICE_CLIENT = "get_service_client"
SERVICE_CLIENT_ALLOWED = (
    "infra/supabase_clients.py",
    "worker.py",
    "services/training_job.py",
    "services/model_registry.py",
    "services/user_admin_service.py",
)
SERVICE_CLIENT_ALLOWED_DIRECTORIES = ("cli/",)


def _is_allowed_service_client_module(relative: str) -> bool:
    return relative in SERVICE_CLIENT_ALLOWED or relative.startswith(
        SERVICE_CLIENT_ALLOWED_DIRECTORIES
    )


def _mentions_service_client(tree: ast.AST) -> bool:
    """True when the name is imported, used as a name, or reached as an attribute."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == SERVICE_CLIENT:
            return True
        if isinstance(node, ast.Attribute) and node.attr == SERVICE_CLIENT:
            return True
        if isinstance(node, ast.ImportFrom | ast.Import) and any(
            alias.name.split(".")[-1] == SERVICE_CLIENT for alias in node.names
        ):
            return True
    return False


def _service_client_offenders(root: Path) -> tuple[int, list[str]]:
    """(number of files scanned, relative paths that mention the service client illegally)."""
    files = sorted(root.rglob("*.py"))
    offenders = [
        relative
        for path in files
        if not _is_allowed_service_client_module(relative := path.relative_to(root).as_posix())
        and _mentions_service_client(ast.parse(path.read_text()))
    ]
    return len(files), offenders


def test_service_client_is_only_imported_by_allowed_modules() -> None:
    scanned, offenders = _service_client_offenders(APP)
    assert scanned > 0, "the guard scanned no file: APP path is wrong"
    assert offenders == []


def test_service_client_guard_detects_every_form_of_violation(tmp_path: Path) -> None:
    violations = {
        "a_from_import.py": "from app.infra.supabase_clients import get_service_client\n",
        "b_attribute.py": (
            "from app.infra import supabase_clients\n"
            "client = supabase_clients.get_service_client()\n"
        ),
        "c_alias.py": "import app.infra.supabase_clients as sc\nsc.get_service_client()\n",
        "d_name.py": "factory = get_service_client\n",
    }
    allowed = {
        "cli/bootstrap_admin.py": "from app.infra.supabase_clients import get_service_client\n"
    }
    for name, source in {**violations, **allowed}.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    scanned, offenders = _service_client_offenders(tmp_path)
    assert scanned == len(violations) + len(allowed)
    assert offenders == sorted(violations)


def test_service_client_is_defined_only_in_supabase_clients_module() -> None:
    definitions = [
        path.relative_to(APP).as_posix()
        for path in APP.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.FunctionDef) and node.name == SERVICE_CLIENT
    ]
    assert definitions == ["infra/supabase_clients.py"]


def test_repositories_never_obtain_the_service_client_themselves() -> None:
    scanned = list((APP / "repositories").rglob("*.py"))
    assert scanned, "the guard scanned no file: repositories path is wrong"
    offenders = [
        path.relative_to(APP).as_posix()
        for path in scanned
        if _mentions_service_client(ast.parse(path.read_text()))
    ]
    assert offenders == []


# --- Phase 1: the raw service-role key (the setting itself, not only the client factory) stays
# inside the same closed list, plus config.py which declares it (ARCHITECTURE 2.5, CLAUDE 4.2) ---

SERVICE_KEY_SETTING = "supabase_service_role_key"


def _reads_service_key_setting(tree: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == SERVICE_KEY_SETTING for n in ast.walk(tree)
    )


def test_service_role_key_setting_is_only_read_by_allowed_modules() -> None:
    allowed = {"config.py", *SERVICE_CLIENT_ALLOWED}
    scanned = sorted(APP.rglob("*.py"))
    assert scanned, "the guard scanned no file: APP path is wrong"
    offenders = [
        relative
        for path in scanned
        if (relative := path.relative_to(APP).as_posix()) not in allowed
        and not relative.startswith(SERVICE_CLIENT_ALLOWED_DIRECTORIES)
        and _reads_service_key_setting(ast.parse(path.read_text()))
    ]
    assert offenders == []


def test_service_role_key_guard_detects_a_violation(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text("key = settings.supabase_service_role_key\n")
    (tmp_path / "fine.py").write_text("key = settings.supabase_anon_key\n")
    flagged = [
        p.name
        for p in sorted(tmp_path.glob("*.py"))
        if _reads_service_key_setting(ast.parse(p.read_text()))
    ]
    assert flagged == ["leak.py"]


def test_readiness_probe_does_not_report_an_expected_outage_to_sentry() -> None:
    """A stopped database is expected (warning log only), never reported with capture()."""
    source = (APP / "services" / "readiness_service.py").read_text()
    names = {n.id for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Name)}
    attributes = {n.attr for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Attribute)}
    assert "capture" not in names | attributes

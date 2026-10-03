"""Guards from docs/TESTING.md section 2 that already make sense in phase 0."""

import ast
from pathlib import Path

import pytest

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


# --- Phase 2: Redis, JWT secret and the authentication modules ---


def test_redis_is_only_imported_under_infra() -> None:
    scanned = sorted(APP.rglob("*.py"))
    assert scanned, "the guard scanned no file: APP path is wrong"
    offenders = [
        relative
        for path in scanned
        if not (relative := path.relative_to(APP).as_posix()).startswith("infra/")
        and any(name.split(".")[0] == "redis" for name in _imports(path))
    ]
    assert offenders == []


SIGNING_KEY_SETTING = "supabase_jwt_secret"


def _reads_jwt_secret_setting(tree: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == SIGNING_KEY_SETTING for n in ast.walk(tree)
    )


def test_jwt_secret_setting_is_only_read_by_the_auth_module() -> None:
    allowed = {"config.py", "infra/auth.py"}
    scanned = sorted(APP.rglob("*.py"))
    assert scanned, "the guard scanned no file: APP path is wrong"
    offenders = [
        relative
        for path in scanned
        if (relative := path.relative_to(APP).as_posix()) not in allowed
        and _reads_jwt_secret_setting(ast.parse(path.read_text()))
    ]
    assert offenders == []
    assert (APP / "infra" / "auth.py").is_file(), "infra/auth.py must exist (phase 2)"
    assert _reads_jwt_secret_setting(ast.parse((APP / "infra" / "auth.py").read_text()))


def test_jwt_secret_guard_detects_a_violation(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text("key = settings.supabase_jwt_secret\n")
    (tmp_path / "fine.py").write_text("key = settings.supabase_jwt_issuer\n")
    flagged = [
        p.name
        for p in sorted(tmp_path.glob("*.py"))
        if _reads_jwt_secret_setting(ast.parse(p.read_text()))
    ]
    assert flagged == ["leak.py"]


def test_infra_auth_does_not_import_supabase_or_redis() -> None:
    path = APP / "infra" / "auth.py"
    assert path.is_file(), "infra/auth.py must exist (phase 2)"
    offenders = [
        name
        for name in _imports(path)
        if name.split(".")[0] in {"supabase", "gotrue", "postgrest", "redis", "httpx"}
    ]
    assert offenders == []


AUTH_MODULES = (
    "infra/auth.py",
    "infra/profile_cache.py",
    "infra/redis_client.py",
    "services/auth_service.py",
    "repositories/profiles_repo.py",
    "api/routes_me.py",
    "schemas/user.py",
    "cli/bootstrap_admin.py",
    "cli/create_test_users.py",
)


@pytest.mark.parametrize("relative", AUTH_MODULES)
def test_the_phase_2_modules_exist_at_the_places_given_by_the_lld(relative: str) -> None:
    assert (APP / relative).is_file()


@pytest.mark.parametrize(
    "relative", ["services/auth_service.py", "repositories/profiles_repo.py", "api/deps.py"]
)
def test_authentication_modules_never_touch_the_service_key(relative: str) -> None:
    path = APP / relative
    assert path.is_file(), f"{relative} must exist (phase 2)"
    tree = ast.parse(path.read_text())
    assert not _mentions_service_client(tree)
    assert not _reads_service_key_setting(tree)


def test_the_api_layer_does_not_import_repositories() -> None:
    """LLD: api -> services -> repositories. Routes and dependencies go through a service."""
    scanned = sorted((APP / "api").rglob("*.py"))
    assert scanned
    offenders = [
        path.relative_to(APP).as_posix()
        for path in scanned
        if any(name.startswith("app.repositories") for name in _imports(path))
    ]
    assert offenders == []


def test_the_cli_commands_hold_no_secret_literal() -> None:
    for relative in ("cli/bootstrap_admin.py", "cli/create_test_users.py"):
        path = APP / relative
        assert path.is_file(), f"{relative} must exist (phase 2)"
        source = path.read_text()
        assert "eyJ" not in source  # no embedded JWT

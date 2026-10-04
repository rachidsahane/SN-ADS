"""Train and activate a first model version, synchronously (demo). Idempotent.

    python -m app.cli.train_demo        # make demo

Does nothing when a version is already active; activates the latest successful version when there
is one; otherwise trains a new one with the same service as the admin button. The service-role
client is allowed here (ARCHITECTURE 2.5, `app/cli/*`).
"""

import sys
from pathlib import Path
from typing import TextIO

from supabase import Client

from app.cli._common import DATABASE_ERRORS, describe_failure
from app.config import ConfigError, get_settings
from app.infra.observability import capture, init_observability
from app.infra.supabase_clients import get_service_client
from app.repositories import model_versions_repo as versions
from app.services.training_job import run_training_job

EXIT_OK = 0
EXIT_FAILURE = 1


def ensure_active_version(db: Client, model_dir: Path) -> str:
    """Returns what was done: 'already active', 'activated' or 'trained and activated'."""
    if versions.active_id(db) is not None:
        return "already active"
    done = "activated"
    version_id = versions.latest_succeeded_id(db)
    if version_id is None:
        version_id = versions.insert_system_queued(db)
        run_training_job(version_id, service_db=db, model_dir=model_dir)
        if versions.latest_succeeded_id(db) != version_id:
            raise RuntimeError("The training did not succeed. See the Models page for the reason.")
        done = "trained and activated"
    versions.set_active(db, version_id)
    return done


def main(*, client: Client | None = None, out: TextIO | None = None) -> int:
    out = out or sys.stdout
    try:
        settings = get_settings()
        done = ensure_active_version(
            client or get_service_client(settings), Path(settings.model_dir)
        )
    except RuntimeError as error:
        print(str(error), file=out)
        return EXIT_FAILURE
    except (*DATABASE_ERRORS, ConfigError) as error:
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    except Exception as error:  # last resort: one line, reported with context
        capture(error, command="train_demo")
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    print(f"Model version: {done}.", file=out)
    return EXIT_OK


if __name__ == "__main__":
    init_observability(get_settings())
    raise SystemExit(main())

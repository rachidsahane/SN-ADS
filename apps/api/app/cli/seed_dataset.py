"""Load the seed CSV into `dataset_rows` (idempotent: rows already there are skipped).

    python -m app.cli.seed_dataset

The CSV path comes from SEED_CSV_PATH (a read-only mount). The service-role client is allowed here
(ARCHITECTURE 2.5, `app/cli/*`).
"""

import sys
from pathlib import Path
from typing import Final, TextIO

import pandas as pd
from supabase import Client

from app.cli._common import DATABASE_ERRORS, describe_failure
from app.config import ConfigError, get_settings
from app.domain.dataset_schema import COLUMN_MAP, ROW_COLUMNS
from app.domain.holdout import is_holdout
from app.infra.observability import capture, init_observability
from app.infra.supabase_clients import get_service_client
from app.repositories import dataset_repo

SOURCE: Final = "seed"
BATCH_SIZE: Final = 1000
EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1


def read_seed_csv(path: Path) -> list[dict[str, object]]:
    """The CSV as `dataset_rows` rows: internal column names, source and test-row flag."""
    frame = pd.read_csv(path).rename(columns=COLUMN_MAP)
    frame["source"] = SOURCE
    frame["is_holdout"] = [is_holdout(SOURCE, int(i)) for i in frame["external_id"]]
    frame["conversion"] = frame["conversion"].astype(int)
    columns = [*ROW_COLUMNS, "source", "conversion"]
    return frame[columns].to_dict("records")  # type: ignore[return-value]


def seed(client: Client, rows: list[dict[str, object]]) -> int:
    """Insert the rows by batches; returns how many were new."""
    before = dataset_repo.count_rows(client, source=SOURCE)
    for start in range(0, len(rows), BATCH_SIZE):
        dataset_repo.insert_rows(client, rows[start : start + BATCH_SIZE])
    return dataset_repo.count_rows(client, source=SOURCE) - before


def main(*, client: Client | None = None, out: TextIO | None = None) -> int:
    out = out or sys.stdout
    try:
        settings = get_settings()
        if not settings.seed_csv_path:
            print(
                "SEED_CSV_PATH is not set (the seed file is mounted by docker compose).", file=out
            )
            return EXIT_FAILURE
        rows = read_seed_csv(Path(settings.seed_csv_path))
        added = seed(client or get_service_client(settings), rows)
    except FileNotFoundError:
        print("The seed file was not found. Check SEED_CSV_PATH.", file=out)
        return EXIT_FAILURE
    except (*DATABASE_ERRORS, ConfigError) as error:
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    except Exception as error:  # last resort: one line, reported with context
        capture(error, command="seed_dataset")
        print(describe_failure(error), file=out)
        return EXIT_FAILURE
    print(f"Seed dataset: {added} rows added, {len(rows) - added} already present.", file=out)
    return EXIT_OK


if __name__ == "__main__":
    init_observability(get_settings())
    raise SystemExit(main())

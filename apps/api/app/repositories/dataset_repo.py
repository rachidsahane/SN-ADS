"""Reads and writes of `public.dataset_rows`. The client is given, never built here (CLAUDE 4.2)."""

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pandas as pd
from postgrest.types import CountMethod, ReturnMethod
from supabase import Client

from app.domain.dataset_schema import ROW_COLUMNS

PAGE_SIZE = 1000


def count_rows(db: Client, *, source: str | None = None, holdout: bool | None = None) -> int:
    query = db.table("dataset_rows").select("id", count=CountMethod.exact).limit(1)
    if source is not None:
        query = query.eq("source", source)
    if holdout is not None:
        query = query.eq("is_holdout", holdout)
    return query.execute().count or 0


def insert_rows(db: Client, rows: Sequence[Mapping[str, Any]]) -> None:
    """Insert rows, silently skipping those whose (source, external_id) already exists."""
    db.table("dataset_rows").upsert(
        list(rows),
        on_conflict="source,external_id",
        ignore_duplicates=True,
        returning=ReturnMethod.minimal,
    ).execute()


def iter_pages(db: Client) -> Iterator[list[dict[str, Any]]]:
    """All rows (the columns a model needs) by pages of 1 000, in a stable order."""
    start = 0
    while True:
        page = (
            db.table("dataset_rows")
            .select(",".join(ROW_COLUMNS))
            .order("external_id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
            .data
        )
        if not page:
            return
        yield page
        start += PAGE_SIZE


def load_frame(db: Client) -> pd.DataFrame:
    return pd.DataFrame([row for page in iter_pages(db) for row in page])

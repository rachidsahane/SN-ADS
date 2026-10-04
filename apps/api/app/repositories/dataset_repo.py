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


def first_loaded_at(db: Client, *, source: str) -> str | None:
    """When the oldest row of `source` was loaded (ISO text), or None when there is none."""
    rows = (
        db.table("dataset_rows")
        .select("created_at")
        .eq("source", source)
        .order("created_at")
        .limit(1)
        .execute()
        .data
    )
    return str(rows[0]["created_at"]) if rows else None


def insert_rows(db: Client, rows: Sequence[Mapping[str, Any]]) -> None:
    """Insert rows, silently skipping those whose (source, external_id) already exists."""
    db.table("dataset_rows").upsert(
        list(rows),
        on_conflict="source,external_id",
        ignore_duplicates=True,
        returning=ReturnMethod.minimal,
    ).execute()


def add_rows(db: Client, rows: Sequence[Mapping[str, Any]]) -> None:
    """Plain insert as the caller (RLS: administrator, source 'agency'). A (source, external_id)
    that already exists raises the unique violation (23505): it is never skipped silently."""
    db.table("dataset_rows").insert(list(rows), returning=ReturnMethod.minimal).execute()


def agency_external_ids(db: Client) -> set[int]:
    """Every external id already imported for the source 'agency' (by pages of 1 000)."""
    found: set[int] = set()
    start = 0
    while True:
        page = (
            db.table("dataset_rows")
            .select("external_id")
            .eq("source", "agency")
            .order("external_id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
            .data
        )
        found.update(int(row["external_id"]) for row in page)
        if len(page) < PAGE_SIZE:
            return found
        start += PAGE_SIZE


def iter_pages(db: Client, *, source: str | None = None) -> Iterator[list[dict[str, Any]]]:
    """All rows (or those of `source`), the columns a model needs, by pages of 1 000, in a stable
    order (external id, then source: the two sources may share an id)."""
    start = 0
    while True:
        query = db.table("dataset_rows").select(",".join(ROW_COLUMNS))
        if source is not None:
            query = query.eq("source", source)
        page = (
            query.order("external_id")
            .order("source")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
            .data
        )
        if not page:
            return
        yield page
        start += PAGE_SIZE


def load_frame(db: Client, *, source: str | None = None) -> pd.DataFrame:
    return pd.DataFrame([row for page in iter_pages(db, source=source) for row in page])

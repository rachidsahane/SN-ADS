"""Validation of an agency CSV file (LLD 5.1, DATA_MODEL 4.3, SECURITY_NOTES 4.3). Pure: bytes in,
rows and issues out. The messages are the ones of the browser pre-check (`csv-check.ts`)."""

import csv
import io
import math
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Final

from app.domain.dataset_schema import CATEGORICAL, COLUMN_MAP, LIMITS

MAX_LISTED_ISSUES: Final = 100
MAX_EXTERNAL_ID: Final = 10**15
MAX_TEXT_LENGTH: Final = 100
FORMULA_PREFIXES: Final = ("=", "+", "-", "@")
ECHO_LENGTH: Final = 40  # a rejected value is repeated in the message, shortened
_NUMBER: Final = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")
_WHOLE: Final = re.compile(r"\d+")

INTEGER_COLUMNS: Final = frozenset(
    {
        "age",
        "income",
        "website_visits",
        "social_shares",
        "email_opens",
        "email_clicks",
        "previous_purchases",
        "loyalty_points",
    }
)
FLOAT_COLUMNS: Final = frozenset({"ad_spend", "pages_per_visit", "time_on_site"})
RATE_COLUMNS: Final = frozenset({"click_through_rate", "conversion_rate"})
TEXT_COLUMNS: Final = frozenset({"advertising_platform", "advertising_tool"})
# Bounds the form does not show: the counts of the table (DATA_MODEL 4.3).
_EXTRA_LIMITS: Final = {"website_visits": {"min": 0, "max": 100_000_000}}

NOT_TEXT = "The file is not a valid UTF-8 CSV text file."
REQUIRED = "Required."
NO_HEADER = "No header row with the expected columns was found."
MISSING = "Column is missing."
UNEXPECTED = "Unexpected column."
TWICE = "Column appears more than once."
NO_ROWS = "The file has no data rows."
TOO_MANY_CELLS = "The row has more values than the header has columns."
NOT_A_NUMBER = "Must be a number."
NOT_WHOLE = "Must be a whole number."
TOO_LONG = f"Use at most {MAX_TEXT_LENGTH} characters."
BAD_ID = f"Must be a whole number from 1 to {MAX_EXTERNAL_ID - 1}."


def _short(value: str) -> str:
    return value if len(value) <= ECHO_LENGTH else value[:ECHO_LENGTH] + "…"


@dataclass(frozen=True)
class CsvIssue:
    row: int  # 1 = header
    column: str
    message: str


@dataclass
class CsvValidation:
    row_count: int = 0
    rows: list[dict[str, object]] = field(default_factory=list)  # internal column names
    issues: list[CsvIssue] = field(default_factory=list)  # the first 100
    total_issues: int = 0
    already_imported: bool = False  # every row is already there and nothing else is wrong


class _Collector:
    def __init__(self) -> None:
        self.result = CsvValidation()

    def add(self, row: int, column: str, message: str) -> None:
        self.result.total_issues += 1
        if len(self.result.issues) < MAX_LISTED_ISSUES:
            self.result.issues.append(CsvIssue(row, column, message))


def _number_error(column: str, value: str) -> str | None:
    """Whole numbers and decimals with their bounds."""
    if not _NUMBER.fullmatch(value) or not math.isfinite(number := float(value)):
        return NOT_A_NUMBER
    if column in INTEGER_COLUMNS and number != int(number):
        return NOT_WHOLE
    limits = LIMITS.get(column) or _EXTRA_LIMITS[column]
    if "min_exclusive" in limits:
        if number <= limits["min_exclusive"]:
            return f"Must be greater than {limits['min_exclusive']}."
        low = limits["min_exclusive"]
    else:
        low = limits["min"]
    return None if low <= number <= limits["max"] else f"Must be between {low} and {limits['max']}."


def _choice_error(column: str, value: str) -> str | None:
    allowed = CATEGORICAL.get(column, ("0", "1"))
    if value in allowed:
        return None
    listed = ", ".join(allowed[:-1]) + f" or {allowed[-1]}"
    return f"Unknown value “{_short(value)}”. Expected {listed}."


def _text_error(value: str) -> str | None:
    if value.startswith(FORMULA_PREFIXES):
        return f"Cell starts with “{value[0]}”; formulas are not allowed."
    return TOO_LONG if len(value) > MAX_TEXT_LENGTH else None


def _cell_error(column: str, value: str) -> str | None:
    """The problem of one non-empty value of a column other than the id, or None."""
    if column in INTEGER_COLUMNS or column in FLOAT_COLUMNS:
        return _number_error(column, value)
    if column in RATE_COLUMNS:
        if not _NUMBER.fullmatch(value):
            return NOT_A_NUMBER
        fraction = 0 <= float(value) <= 1
        return None if fraction else f"Must be a fraction between 0 and 1 (got {_short(value)})."
    if column in CATEGORICAL or column == "conversion":
        return _choice_error(column, value)
    return _text_error(value)


def _convert(column: str, value: str) -> object:
    if column in INTEGER_COLUMNS or column == "conversion":
        return int(float(value))
    if column in FLOAT_COLUMNS or column in RATE_COLUMNS:
        return float(value)
    return value


def _check_header(header: list[str], out: _Collector) -> bool:
    """True when the header is exactly the 20 expected names (any order)."""
    expected = list(COLUMN_MAP)
    missing = [name for name in expected if name not in header]
    if not header or len(missing) == len(expected):
        out.add(1, "—", NO_HEADER)
        return False
    for name in missing:
        out.add(1, name, MISSING)
    seen: set[str] = set()
    for name in header:
        if name in seen:
            out.add(1, name, TWICE)
        elif name not in COLUMN_MAP:
            out.add(1, _short(name), UNEXPECTED)
        seen.add(name)
    return out.result.total_issues == 0


def _read_records(content: bytes, out: _Collector) -> list[tuple[int, list[str]]] | None:
    """The non-blank records with the file line where each ends, or None (issue added)."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = "\x00"
    if "\x00" in text:
        out.add(1, "—", NOT_TEXT)
        return None
    reader = csv.reader(io.StringIO(text, newline=""))
    records: list[tuple[int, list[str]]] = []
    try:
        for record in reader:
            if any(cell.strip() for cell in record):
                records.append((reader.line_num, record))
    except csv.Error:
        out.add(max(reader.line_num, 1), "—", NOT_TEXT)
        return None
    return records


class _Ids:
    """The campaign numbers of the file, against each other and against those already imported."""

    def __init__(self, existing: Collection[int]) -> None:
        self.seen: set[int] = set()
        self.existing = existing
        self.already_there = 0

    def check(self, raw: str) -> tuple[int | None, str | None]:
        """(the id, None) when it is usable, otherwise (None, the problem). An id that was
        imported before is usable here: it is counted and reported by the caller."""
        if not _WHOLE.fullmatch(raw) or not 1 <= int(raw) < MAX_EXTERNAL_ID:
            return None, BAD_ID
        identifier = int(raw)
        if identifier in self.seen:
            return None, f"Duplicate campaign number {identifier}."
        self.seen.add(identifier)
        return identifier, None


def _check_row(
    line: int, header: list[str], cells: list[str], ids: _Ids, out: _Collector
) -> tuple[dict[str, object] | None, int]:
    """(the row when every cell is fine, number of issues other than "id already imported")."""
    other = 0
    if len(cells) > len(header):
        out.add(line, "—", TOO_MANY_CELLS)
        other += 1
    values = {
        COLUMN_MAP[name]: (cells[index].strip() if index < len(cells) else "")
        for index, name in enumerate(header)
    }
    row: dict[str, object] = {}
    for csv_name, column in COLUMN_MAP.items():
        raw = values[column]
        message: str | None = REQUIRED if raw == "" else None
        if message is None and column == "external_id":
            identifier, message = ids.check(raw)
            if identifier is not None:
                row[column] = identifier
                if identifier in ids.existing:
                    out.add(line, csv_name, f"Campaign number {identifier} was already imported.")
                    ids.already_there += 1
        elif message is None:
            message = _cell_error(column, raw)
            if message is None:
                row[column] = _convert(column, raw)
        if message:
            out.add(line, csv_name, message)
            other += 1
    return (row if len(row) == len(COLUMN_MAP) else None), other


def validate_csv(content: bytes, existing_ids: Collection[int]) -> CsvValidation:
    """Check the whole file. `existing_ids`: ids already imported for the source 'agency'.

    Row numbers are file lines (1 = header). Valid rows come back with the internal column names
    and typed values; they are only meant to be used when `total_issues == 0`.
    """
    out = _Collector()
    result = out.result
    records = _read_records(content, out)
    if records is None:
        return result
    header = [name.strip() for name in records[0][1]] if records else []
    data = records[1:]
    result.row_count = len(data)
    if not _check_header(header, out):
        return result
    if not data:
        out.add(2, "—", NO_ROWS)
        return result

    ids = _Ids(existing_ids)
    other_issues = 0
    for line, cells in data:
        row, other = _check_row(line, header, cells, ids, out)
        other_issues += other
        if row is not None:
            result.rows.append(row)
    if other_issues == 0 and ids.already_there == len(data):
        result.already_imported = True
        result.issues.clear()
        result.total_issues = 0
    return result

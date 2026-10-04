"""domain/csv_validation.py: the whole-file check of an agency CSV (pure, no database)."""

import csv
import io
from pathlib import Path

import pytest

from app.domain.csv_validation import MAX_LISTED_ISSUES, validate_csv
from app.domain.dataset_schema import COLUMN_MAP

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HEADER = list(COLUMN_MAP)
GOOD = [
    "7", "30", "Female", "50000", "Email", "Awareness", "1500.5", "0.12", "0.05", "20",
    "3.5", "4.2", "10", "5", "2", "1", "300", "IsConfid", "ToolConfid", "1",
]  # fmt: skip


def make_csv(*rows: list[str], header: list[str] | None = None) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header or HEADER)
    writer.writerows(rows)
    return out.getvalue().encode()


def with_cell(column: str, value: str, base: list[str] | None = None) -> list[str]:
    row = list(base or GOOD)
    row[HEADER.index(column)] = value
    return row


def messages(content: bytes, existing: set[int] | None = None) -> list[tuple[int, str, str]]:
    result = validate_csv(content, existing or set())
    return [(i.row, i.column, i.message) for i in result.issues]


def test_a_valid_file_gives_typed_rows_with_the_internal_names() -> None:
    result = validate_csv(make_csv(GOOD), set())
    assert result.total_issues == 0
    assert result.row_count == 1
    assert result.rows == [
        {
            "external_id": 7, "age": 30, "gender": "Female", "income": 50000,
            "campaign_channel": "Email", "campaign_type": "Awareness", "ad_spend": 1500.5,
            "click_through_rate": 0.12, "conversion_rate": 0.05, "website_visits": 20,
            "pages_per_visit": 3.5, "time_on_site": 4.2, "social_shares": 10, "email_opens": 5,
            "email_clicks": 2, "previous_purchases": 1, "loyalty_points": 300,
            "advertising_platform": "IsConfid", "advertising_tool": "ToolConfid", "conversion": 1,
        }
    ]  # fmt: skip


def test_the_sample_files_of_the_demo() -> None:
    good = validate_csv((FIXTURES / "small_dataset.csv").read_bytes(), set())
    assert (good.total_issues, good.row_count, len(good.rows)) == (0, 400, 400)
    bad = validate_csv((FIXTURES / "small_dataset_invalid.csv").read_bytes(), set())
    assert [(i.row, i.column) for i in bad.issues] == [
        (3, "ClickThroughRate"),
        (5, "AdvertisingPlatform"),
    ]


def test_a_bom_a_different_column_order_and_crlf_are_accepted() -> None:
    order = list(reversed(HEADER))
    text = ",".join(order) + "\r\n" + ",".join(GOOD[HEADER.index(c)] for c in order) + "\r\n"
    result = validate_csv(b"\xef\xbb\xbf" + text.encode(), set())
    assert result.total_issues == 0
    assert result.rows[0]["external_id"] == 7


@pytest.mark.parametrize(
    ("column", "value", "expected"),
    [
        ("CustomerID", "0", "Must be a whole number from 1 to 999999999999999."),
        ("CustomerID", "abc", "Must be a whole number from 1 to 999999999999999."),
        ("CustomerID", "1e30", "Must be a whole number from 1 to 999999999999999."),
        ("Age", "17", "Must be between 18 and 100."),
        ("Age", "30.5", "Must be a whole number."),
        ("Age", "thirty", "Must be a number."),
        ("Age", "nan", "Must be a number."),
        ("Age", "1_0", "Must be a number."),
        ("Income", "-1", "Must be between 0 and 100000000."),
        ("AdSpend", "0", "Must be greater than 0."),
        ("AdSpend", "10000001", "Must be between 0 and 10000000."),
        ("ClickThroughRate", "5", "Must be a fraction between 0 and 1 (got 5)."),
        ("ConversionRate", "-0.1", "Must be a fraction between 0 and 1 (got -0.1)."),
        ("ConversionRate", "five", "Must be a number."),
        ("WebsiteVisits", "100000001", "Must be between 0 and 100000000."),
        ("PagesPerVisit", "1001", "Must be between 0 and 1000."),
        ("TimeOnSite", "1441", "Must be between 0 and 1440."),
        ("PreviousPurchases", "10001", "Must be between 0 and 10000."),
        ("Gender", "Other", "Unknown value “Other”. Expected Male or Female."),
        (
            "CampaignChannel",
            "TV",
            "Unknown value “TV”. Expected Social Media, Email, PPC, SEO or Referral.",
        ),
        (
            "CampaignType",
            "email",
            "Unknown value “email”. Expected Awareness, Consideration, Conversion or Retention.",
        ),
        ("Conversion", "2", "Unknown value “2”. Expected 0 or 1."),
        ("AdvertisingPlatform", "x" * 101, "Use at most 100 characters."),
        ("AdvertisingTool", "", "Required."),
    ],
)
def test_each_rule_reports_the_row_the_column_and_a_sentence(
    column: str, value: str, expected: str
) -> None:
    assert messages(make_csv(with_cell(column, value))) == [(2, column, expected)]


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_a_text_cell_that_starts_like_a_formula_is_refused(prefix: str) -> None:
    content = make_csv(with_cell("AdvertisingPlatform", f"{prefix}SUM(A1)"))
    assert messages(content) == [
        (2, "AdvertisingPlatform", f"Cell starts with “{prefix}”; formulas are not allowed.")
    ]


def test_a_negative_number_is_not_a_formula() -> None:
    assert messages(make_csv(with_cell("Income", "-5"))) == [
        (2, "Income", "Must be between 0 and 100000000.")
    ]


def test_the_same_id_twice_in_the_file_is_reported_on_the_second_row() -> None:
    content = make_csv(GOOD, with_cell("Age", "31"))
    assert messages(content) == [(3, "CustomerID", "Duplicate campaign number 7.")]


def test_ids_already_imported_are_reported_row_by_row() -> None:
    content = make_csv(GOOD, with_cell("CustomerID", "8"))
    result = validate_csv(content, {7})
    assert not result.already_imported
    assert [(i.row, i.message) for i in result.issues] == [
        (2, "Campaign number 7 was already imported.")
    ]


def test_a_file_whose_rows_are_all_already_imported_is_flagged_as_such() -> None:
    content = make_csv(GOOD, with_cell("CustomerID", "8"))
    result = validate_csv(content, {7, 8, 9})
    assert result.already_imported
    assert (result.total_issues, result.issues) == (0, [])


def test_an_invalid_row_with_an_existing_id_is_not_an_already_imported_file() -> None:
    content = make_csv(with_cell("Age", "5"))
    result = validate_csv(content, {7})
    assert not result.already_imported
    assert result.total_issues == 2


def test_missing_unexpected_and_repeated_columns() -> None:
    header = [name for name in HEADER if name != "Age"] + ["Colour", "Income"]
    result = validate_csv(make_csv(header=header), set())
    assert [(i.row, i.column, i.message) for i in result.issues] == [
        (1, "Age", "Column is missing."),
        (1, "Colour", "Unexpected column."),
        (1, "Income", "Column appears more than once."),
    ]


def test_a_file_without_the_expected_header() -> None:
    result = validate_csv(b"a,b\n1,2\n", set())
    assert [(i.row, i.column, i.message) for i in result.issues] == [
        (1, "—", "No header row with the expected columns was found.")
    ]
    assert validate_csv(b"", set()).total_issues == 1


def test_a_file_with_a_header_only_has_no_rows() -> None:
    result = validate_csv(make_csv(), set())
    assert [(i.row, i.column, i.message) for i in result.issues] == [
        (2, "—", "The file has no data rows.")
    ]


def test_a_short_row_has_required_cells_and_a_long_row_is_refused() -> None:
    assert messages(make_csv(GOOD[:18]))[0] == (2, "AdvertisingTool", "Required.")
    assert messages(make_csv([*GOOD, "extra"])) == [
        (2, "—", "The row has more values than the header has columns.")
    ]


def test_blank_lines_are_ignored() -> None:
    content = make_csv(GOOD) + b"\n\n,,,\n"
    assert validate_csv(content, set()).total_issues == 0


@pytest.mark.parametrize("content", [b"\xff\xfe\x00bad", b"CustomerID\x00,Age\n"])
def test_a_file_that_is_not_text_is_refused(content: bytes) -> None:
    result = validate_csv(content, set())
    assert [(i.column, i.message) for i in result.issues] == [
        ("—", "The file is not a valid UTF-8 CSV text file.")
    ]


def test_a_value_repeated_in_a_message_is_shortened() -> None:
    result = validate_csv(make_csv(with_cell("Gender", "x" * 500)), set())
    assert len(result.issues[0].message) < 120


def test_only_the_first_100_issues_are_listed_but_all_are_counted() -> None:
    rows = [with_cell("CustomerID", str(i), with_cell("Age", "5")) for i in range(1, 151)]
    result = validate_csv(make_csv(*rows), set())
    assert len(result.issues) == MAX_LISTED_ISSUES
    assert result.total_issues == 150
    assert result.issues[0].row == 2

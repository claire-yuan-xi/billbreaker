import pytest

from billbreaker.services.bill_query import Query, parse_query
from billbreaker.services.bill_sources import current_congress
from billbreaker.validation import normalize_bill_no, split_congress


@pytest.mark.parametrize(
    "state, typed, expected",
    [
        ("US", "MI 1245", Query("MI", number="1245")),
        ("US", "Michigan SB 1245", Query("MI", bill_no="SB 1245")),
        ("US", "michigan senate bill 1245", Query("MI", bill_no="SB 1245")),
        ("US", "hb 12 michigan", Query("MI", bill_no="HB 12")),
        ("US", "HB 1 TX", Query("TX", bill_no="HB 1")),
        ("US", "West Virginia HB 2", Query("WV", bill_no="HB 2")),
        ("US", "Virginia HB 2", Query("VA", bill_no="HB 2")),
        ("US", "H.R. 1", Query("US", bill_no="HR 1")),
        ("US", "US HR 1", Query("US", bill_no="HR 1")),
        ("US", "house bill 5", Query("US", bill_no="HR 5")),
        ("US", "S. 5", Query("US", bill_no="S 5")),
        ("US", "1245", Query("US", number="1245")),
        ("US", "bill #1245", Query("US", number="1245")),
        ("US", "HB 1 2025", Query("US", bill_no="HR 1")),
        ("US", "SB 2025", Query("US", bill_no="S 2025")),
        ("US", "Laken Riley Act", Query("US", words="Laken Riley Act")),
        ("MI", "1245", Query("MI", number="1245")),
        ("TX", "TX hb1", Query("TX", bill_no="HB 1")),
        ("TX", "HB 1 89th", Query("TX", bill_no="HB 1")),
        ("CA", "AB-5", Query("CA", bill_no="AB 5")),
        # From California's picker, "AR 5" is California's own Assembly Resolution 5.
        ("CA", "AR 5", Query("CA", bill_no="AR 5")),
        ("US", "AR 5", Query("AR", number="5")),
        ("NY", "S3000A", Query("NY", bill_no="S 3000A")),
        ("US", "New York A 1", Query("NY", bill_no="A 1")),
    ],
)
def test_reads_what_people_type(state, typed, expected):
    assert parse_query(state, typed) == expected


def test_an_older_congress_is_kept_with_the_bill():
    assert parse_query("US", "HR 5376 117th Congress") == Query("US", bill_no="HR 5376 (117th)", congress=117)
    assert parse_query("CA", "117th congress H.R. 5376").bill_no == "HR 5376 (117th)"
    now = current_congress()
    assert parse_query("US", f"HR 1 ({now}th)").bill_no == "HR 1"


def test_bill_numbers_keep_their_congress():
    assert normalize_bill_no("h.r. 5376 (117th)") == "HR 5376 (117th)"
    assert normalize_bill_no("HR 5376 (117)") == "HR 5376 (117th)"
    assert split_congress("HR 5376 (117th)") == ("HR 5376", 117)
    assert split_congress("HB 12") == ("HB 12", None)

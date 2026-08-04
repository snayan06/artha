from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from artha_api.models import Account, AccountKind, HouseholdMember
from artha_api.parser import ParseError, parse_transaction

FIXED_NOW = datetime(2026, 8, 4, 18, 30, tzinfo=UTC)
ACCOUNT = Account(id=1, user_id="demo-user", name="HDFC UPI", kind=AccountKind.BANK)
AVERY = HouseholdMember(id=1, user_id="demo-user", name="Avery")
JORDAN = HouseholdMember(id=2, user_id="demo-user", name="Jordan")


@pytest.mark.parametrize(
    ("date_phrase", "expected"),
    [
        ("today", datetime(2026, 8, 4, tzinfo=UTC)),
        ("yesterday", datetime(2026, 8, 3, tzinfo=UTC)),
        ("day before yesterday", datetime(2026, 8, 2, tzinfo=UTC)),
        ("on 2025-12-31", datetime(2025, 12, 31, tzinfo=UTC)),
        ("on 2 Aug", datetime(2026, 8, 2, tzinfo=UTC)),
        ("on 2 August", datetime(2026, 8, 2, tzinfo=UTC)),
    ],
)
def test_parser_supports_unambiguous_dates(date_phrase: str, expected: datetime) -> None:
    parsed = parse_transaction(
        f"Paid 500 for groceries from HDFC UPI {date_phrase}",
        [ACCOUNT],
        now=FIXED_NOW,
    )

    assert parsed.draft.occurred_at == expected
    assert parsed.draft.occurred_at is not None
    assert parsed.draft.occurred_at.tzinfo is UTC


def test_parser_leaves_date_unset_when_absent() -> None:
    parsed = parse_transaction(
        "Paid 500 for groceries from HDFC UPI", [ACCOUNT], now=FIXED_NOW
    )

    assert parsed.draft.occurred_at is None


def test_yearless_date_uses_most_recent_past_occurrence() -> None:
    january_now = datetime(2026, 1, 2, 18, 30, tzinfo=UTC)

    parsed = parse_transaction(
        "Paid 500 for groceries from HDFC UPI on 31 Dec",
        [ACCOUNT],
        now=january_now,
    )

    assert parsed.draft.occurred_at == datetime(2025, 12, 31, tzinfo=UTC)


def test_relative_date_uses_callers_local_calendar_day() -> None:
    india_now = datetime(2026, 8, 5, 0, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    parsed = parse_transaction(
        "Paid 500 for groceries from HDFC UPI today",
        [ACCOUNT],
        now=india_now,
    )

    assert parsed.draft.occurred_at == datetime(2026, 8, 5, tzinfo=UTC)


def test_parser_recognizes_member_paid_shared_expense() -> None:
    parsed = parse_transaction(
        "Avery paid 1000 for dinner, split equally with Avery from HDFC UPI",
        [ACCOUNT],
        [AVERY, JORDAN],
        now=FIXED_NOW,
    )

    assert parsed.draft.paid_by_member_id == AVERY.id
    assert parsed.draft.personal_share_paise == 50_000
    assert [split.model_dump() for split in parsed.draft.splits] == [
        {"member_id": AVERY.id, "amount_paise": 50_000}
    ]


def test_equal_split_distributes_odd_paise_without_losing_money() -> None:
    parsed = parse_transaction(
        "Paid 100.01 for dinner from HDFC UPI, split equally with Avery and Jordan",
        [ACCOUNT],
        [AVERY, JORDAN],
        now=FIXED_NOW,
    )

    split_amounts = [split.amount_paise for split in parsed.draft.splits]
    assert parsed.draft.personal_share_paise == 3_334
    assert split_amounts == [3_334, 3_333]
    assert parsed.draft.personal_share_paise + sum(split_amounts) == 10_001


def test_equal_split_requires_a_recognized_household_member() -> None:
    with pytest.raises(ParseError, match="recognized household member"):
        parse_transaction(
            "Paid 500 for dinner from HDFC UPI, split equally with Unknown Person",
            [ACCOUNT],
            [AVERY],
            now=FIXED_NOW,
        )


def test_parser_recognizes_member_settlement() -> None:
    parsed = parse_transaction(
        "Avery paid 500 as settlement into HDFC UPI",
        [ACCOUNT],
        [AVERY],
        now=FIXED_NOW,
    )

    assert parsed.draft.kind.value == "settlement"
    assert parsed.draft.paid_by_member_id is None
    assert parsed.draft.settlement_member_id == AVERY.id
    assert parsed.draft.settlement_direction is not None
    assert parsed.draft.settlement_direction.value == "received"


@pytest.mark.parametrize(
    ("date_phrase", "expected_day"),
    [("3 days ago", 1), ("3 days back", 1), ("0 days ago", 4), ("100 days back", 26)],
)
def test_parser_supports_safe_integer_relative_dates(
    date_phrase: str, expected_day: int
) -> None:
    parsed = parse_transaction(
        f"Paid 500 for groceries from HDFC UPI {date_phrase}",
        [ACCOUNT],
        now=FIXED_NOW,
    )

    assert parsed.draft.occurred_at is not None
    assert parsed.draft.occurred_at.day == expected_day


def test_parser_rejects_unsafe_relative_date() -> None:
    with pytest.raises(ParseError, match="too far"):
        parse_transaction(
            "Paid 500 for groceries from HDFC UPI 36501 days ago",
            [ACCOUNT],
            now=FIXED_NOW,
        )


@pytest.mark.parametrize("date_phrase", ["on 02/08/2026", "on 8-2-26", "on 2026-02-30"])
def test_parser_rejects_ambiguous_or_invalid_dates(date_phrase: str) -> None:
    with pytest.raises(ParseError):
        parse_transaction(
            f"Paid 500 for groceries from HDFC UPI {date_phrase}",
            [ACCOUNT],
            now=FIXED_NOW,
        )

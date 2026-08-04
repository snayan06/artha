from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .models import (
    Account,
    HouseholdMember,
    MerchantMatchType,
    MerchantRule,
    SettlementDirection,
    TransactionKind,
)
from .schemas import ParseResponse, TransactionDraft, TransactionSplitInput

AMOUNT_PATTERN = re.compile(r"(?:₹|rs\.?\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
FOR_PATTERN = re.compile(
    r"\b(?:for|on)\s+(.+?)(?=\s+from\s+|,|\s+split\s+|\s+with\s+|$)", re.IGNORECASE
)
CATEGORY_ALIASES = {
    "grocery": "Groceries",
    "groceries": "Groceries",
    "food": "Food & Dining",
    "dinner": "Food & Dining",
    "lunch": "Food & Dining",
    "rent": "Housing",
    "uber": "Transport",
    "cab": "Transport",
    "salary": "Salary",
    "shopping": "Shopping",
}
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))


class ParseError(ValueError):
    pass


def amount_to_paise(raw: str) -> int:
    try:
        rupees = Decimal(raw.replace(",", ""))
    except InvalidOperation as error:
        raise ParseError("could not understand the amount") from error
    paise = int((rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if paise <= 0:
        raise ParseError("amount must be positive")
    return paise


def _account_for_text(text: str, accounts: list[Account]) -> tuple[Account, list[str]]:
    normalized = text.casefold()
    for account in sorted(accounts, key=lambda item: len(item.name), reverse=True):
        if account.name.casefold() in normalized:
            return account, []
        tokens = [token for token in re.split(r"\W+", account.name.casefold()) if len(token) > 2]
        if tokens and all(token in normalized for token in tokens):
            return account, []
    if not accounts:
        raise ParseError("create an account before parsing a transaction")
    return accounts[0], [f"Account was not explicit; using {accounts[0].name}."]


def _description(text: str, kind: TransactionKind) -> str:
    description_match = FOR_PATTERN.search(text)
    if description_match:
        description = description_match.group(1).strip(" .")
    elif kind is TransactionKind.INCOME:
        description = "Income"
    elif kind is TransactionKind.SETTLEMENT:
        description = "Household settlement"
    else:
        description = "Expense"
    return description.capitalize()


def _heuristic_category(description: str) -> str | None:
    lowered = description.casefold()
    return next((value for key, value in CATEGORY_ALIASES.items() if key in lowered), None)


def _normalize_merchant(value: str) -> str:
    return " ".join(value.casefold().split())


def _matching_rule(
    merchant: str, account_id: int, rules: list[MerchantRule]
) -> MerchantRule | None:
    normalized_merchant = _normalize_merchant(merchant)
    matches = [
        rule
        for rule in rules
        if rule.active
        and (rule.account_id is None or rule.account_id == account_id)
        and (
            (
                rule.match_type is MerchantMatchType.EXACT
                and normalized_merchant == _normalize_merchant(rule.merchant_pattern)
            )
            or (
                rule.match_type is MerchantMatchType.CONTAINS
                and _normalize_merchant(rule.merchant_pattern) in normalized_merchant
            )
        )
    ]
    if not matches:
        return None
    return min(
        matches,
        key=lambda rule: (
            -rule.priority,
            -(rule.account_id is not None),
            -len(rule.merchant_pattern),
            rule.id,
        ),
    )


def _midnight_utc(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _parse_occurred_at(text: str, now: datetime) -> datetime | None:
    normalized = text.casefold()
    ambiguous_numeric = re.search(
        r"\bon\s+\d{1,2}\s*[/-]\s*\d{1,2}(?:\s*[/-]\s*\d{2,4})?\b",
        normalized,
    )
    if ambiguous_numeric:
        raise ParseError("ambiguous numeric dates are not supported; use YYYY-MM-DD")

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
    if iso_match:
        try:
            return _midnight_utc(date.fromisoformat(iso_match.group(1)))
        except ValueError as error:
            raise ParseError("date is invalid") from error

    today = now.date()
    if re.search(r"\bday\s+before\s+yesterday\b", normalized):
        return _midnight_utc(today - timedelta(days=2))
    if re.search(r"\byesterday\b", normalized):
        return _midnight_utc(today - timedelta(days=1))
    if re.search(r"\btoday\b", normalized):
        return _midnight_utc(today)

    relative_days = re.search(r"\b(\d+)\s+days?\s+(?:ago|back)\b", normalized)
    if relative_days:
        days = int(relative_days.group(1))
        if days > 36_500:
            raise ParseError("relative date is too far in the past")
        return _midnight_utc(today - timedelta(days=days))

    named_date = re.search(
        rf"\bon\s+(\d{{1,2}})\s+({MONTH_PATTERN})\b",
        normalized,
    )
    if named_date:
        try:
            return _midnight_utc(
                date(today.year, MONTHS[named_date.group(2)], int(named_date.group(1)))
            )
        except ValueError as error:
            raise ParseError("date is invalid") from error
    return None


def parse_transaction(
    text: str,
    accounts: list[Account],
    members: list[HouseholdMember] | None = None,
    merchant_rules: list[MerchantRule] | None = None,
    *,
    now: datetime | None = None,
) -> ParseResponse:
    amount_match = AMOUNT_PATTERN.search(text)
    if amount_match is None:
        raise ParseError("include an amount, for example: Paid 1840 for groceries")
    amount_paise = amount_to_paise(amount_match.group(1))
    normalized = text.casefold()
    account, warnings = _account_for_text(text, accounts)
    occurred_at = _parse_occurred_at(text, now or datetime.now(UTC))
    available_members = members or []
    mentioned_members = sorted(
        (
            member
            for member in available_members
            if re.search(rf"\b{re.escape(member.name.casefold())}\b", normalized)
        ),
        key=lambda member: normalized.find(member.name.casefold()),
    )
    paid_by_member = next(
        (
            member
            for member in available_members
            if re.search(
                rf"\b{re.escape(member.name.casefold())}\s+paid\b", normalized
            )
        ),
        None,
    )
    paid_member = next(
        (
            member
            for member in available_members
            if re.search(
                rf"\bpaid\s+{re.escape(member.name.casefold())}\b", normalized
            )
        ),
        None,
    )

    if any(word in normalized for word in ("salary", "received income", "earned")):
        kind = TransactionKind.INCOME
    elif "settle" in normalized or "settlement" in normalized or paid_member is not None:
        kind = TransactionKind.SETTLEMENT
    else:
        kind = TransactionKind.EXPENSE

    equally = bool(re.search(r"split\s+(?:it\s+)?equally|equal\s+split|50\s*/\s*50", normalized))
    if equally and kind is TransactionKind.EXPENSE:
        if not mentioned_members:
            raise ParseError("equal split requires at least one recognized household member")
        participant_count = len(mentioned_members) + 1
        base_share, remainder = divmod(amount_paise, participant_count)
        if base_share == 0:
            raise ParseError("amount is too small to split across the selected members")
        personal_share_paise = base_share + (1 if remainder else 0)
        remaining_remainder = max(0, remainder - 1)
        splits = [
            TransactionSplitInput(
                member_id=member.id,
                amount_paise=base_share + (1 if index < remaining_remainder else 0),
            )
            for index, member in enumerate(mentioned_members)
        ]
    else:
        personal_share_paise = amount_paise
        splits = []

    settlement_direction: SettlementDirection | None = None
    if kind is TransactionKind.SETTLEMENT:
        settlement_member = paid_member or (mentioned_members[0] if mentioned_members else None)
        if settlement_member is None:
            raise ParseError("settlement requires a recognized household member")
        settlement_direction = (
            SettlementDirection.RECEIVED
            if "received" in normalized
            or paid_by_member is not None
            else SettlementDirection.PAID
        )
        personal_share_paise = amount_paise
        splits = []
    else:
        settlement_member = None

    description = _description(text, kind)
    matched_rule = _matching_rule(description, account.id, merchant_rules or [])
    heuristic_category = None if matched_rule is not None else _heuristic_category(description)
    category = matched_rule.category if matched_rule is not None else heuristic_category
    if category is None and kind in {TransactionKind.EXPENSE, TransactionKind.INCOME}:
        warnings.append("Category could not be inferred; review before confirming.")

    draft = TransactionDraft(
        kind=kind,
        amount_paise=amount_paise,
        description=description,
        category=category,
        paid_by_member_id=(
            paid_by_member.id
            if kind is TransactionKind.EXPENSE and paid_by_member is not None
            else None
        ),
        settlement_member_id=(
            settlement_member.id if settlement_member is not None else None
        ),
        personal_share_paise=personal_share_paise,
        splits=splits,
        source_account_id=account.id,
        settlement_direction=settlement_direction,
        occurred_at=occurred_at,
        notes=f"Parsed from: {text}",
    )
    confidence = 0.97 if not warnings else 0.78
    return ParseResponse(
        draft=draft,
        confidence=confidence,
        warnings=warnings,
        category_source=(
            "merchant_rule"
            if matched_rule is not None
            else "heuristic"
            if heuristic_category is not None
            else None
        ),
        matched_merchant_rule_id=matched_rule.id if matched_rule is not None else None,
    )

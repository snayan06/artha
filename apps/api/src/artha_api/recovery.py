from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecoveryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecoveryHousehold(RecoveryModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("household name cannot be blank")
        return normalized


class RecoveryProfile(RecoveryModel):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("profile display name cannot be blank")
        return normalized


class RecoveryMember(RecoveryModel):
    source_id: UUID
    display_name: str = Field(min_length=1, max_length=100)
    member_type: Literal["user", "participant"]
    role: Literal["owner", "member"]
    is_active: bool

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("member display name cannot be blank")
        return normalized


class RecoveryAccount(RecoveryModel):
    source_id: UUID
    name: str = Field(min_length=1, max_length=100)
    account_type: Literal["cash", "bank", "wallet", "credit_card", "other"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    opening_balance_paise: int
    credit_limit_paise: int | None = Field(default=None, ge=0)
    statement_day: int | None = Field(default=None, ge=1, le=31)
    payment_due_day: int | None = Field(default=None, ge=1, le=31)
    is_archived: bool
    created_at: datetime

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("account name cannot be blank")
        return normalized

    @model_validator(mode="after")
    def card_metadata_matches_type(self) -> RecoveryAccount:
        card_values = (
            self.credit_limit_paise,
            self.statement_day,
            self.payment_due_day,
        )
        if self.account_type != "credit_card" and any(value is not None for value in card_values):
            raise ValueError("card metadata is valid only for credit_card accounts")
        if self.account_type == "credit_card" and self.opening_balance_paise > 0:
            raise ValueError("credit_card opening balance cannot be positive")
        return self


class RecoveryCategory(RecoveryModel):
    source_id: UUID
    name: str = Field(min_length=1, max_length=80)
    category_type: Literal["expense", "income", "both"]
    icon: str | None = Field(default=None, max_length=80)
    is_archived: bool
    created_at: datetime

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("category name cannot be blank")
        return normalized


class RecoveryTransaction(RecoveryModel):
    source_id: UUID
    account_source_id: UUID
    category_source_id: UUID | None = None
    paid_by_member_source_id: UUID | None = None
    direction: Literal[
        "expense",
        "income",
        "transfer_out",
        "transfer_in",
        "settlement_out",
        "settlement_in",
    ]
    amount_paise: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    occurred_at: datetime
    merchant: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=1000)
    status: Literal["posted", "voided"]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    voided_at: datetime | None = None

    @model_validator(mode="after")
    def transaction_shape(self) -> RecoveryTransaction:
        cashflow = self.direction in {"expense", "income"}
        if cashflow != (self.category_source_id is not None):
            raise ValueError("expense and income require a category; other directions forbid it")
        if cashflow and self.paid_by_member_source_id is None:
            raise ValueError("expense and income require a payer")
        if (self.status == "voided") != (self.voided_at is not None):
            raise ValueError("voided_at must match transaction status")
        return self


class RecoverySplit(RecoveryModel):
    transaction_source_id: UUID
    member_source_id: UUID
    amount_paise: int = Field(gt=0)


class RecoveryTransfer(RecoveryModel):
    source_id: UUID
    out_transaction_source_id: UUID
    in_transaction_source_id: UUID
    created_at: datetime


class RecoverySettlement(RecoveryModel):
    source_id: UUID
    payer_member_source_id: UUID
    payee_member_source_id: UUID
    account_source_id: UUID | None = None
    transaction_source_id: UUID | None = None
    account_direction: Literal["settlement_out", "settlement_in"] | None = None
    amount_paise: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    settled_at: datetime
    note: str | None = Field(default=None, max_length=1000)
    created_at: datetime


class RecoveryMerchantRule(RecoveryModel):
    source_id: UUID
    match_type: Literal["exact", "contains", "regex"]
    merchant_pattern: str = Field(min_length=1, max_length=160)
    category_source_id: UUID
    account_source_id: UUID | None = None
    priority: int = Field(ge=0, le=10_000)
    is_active: bool
    created_at: datetime

    @field_validator("merchant_pattern")
    @classmethod
    def normalize_pattern(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("merchant pattern cannot be blank")
        return normalized


class RecoveryAuditEvent(RecoveryModel):
    source_id: int = Field(gt=0)
    entity_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    entity_source_id: UUID | None = None
    action: str = Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class RecoveryBundle(RecoveryModel):
    format: Literal["artha-recovery"]
    schema_version: Literal[1]
    exported_at: datetime
    household: RecoveryHousehold
    profile: RecoveryProfile
    members: list[RecoveryMember] = Field(min_length=1, max_length=100)
    accounts: list[RecoveryAccount] = Field(min_length=1, max_length=100)
    categories: list[RecoveryCategory] = Field(min_length=1, max_length=200)
    transactions: list[RecoveryTransaction] = Field(max_length=50_000)
    splits: list[RecoverySplit] = Field(max_length=100_000)
    transfers: list[RecoveryTransfer] = Field(max_length=50_000)
    settlements: list[RecoverySettlement] = Field(max_length=50_000)
    merchant_rules: list[RecoveryMerchantRule] = Field(max_length=5_000)
    audit_events: list[RecoveryAuditEvent] = Field(max_length=100_000)

    @model_validator(mode="after")
    def references_are_closed(self) -> RecoveryBundle:
        self._validate_unique_source_ids()
        member_by_id = {item.source_id: item for item in self.members}
        account_by_id = {item.source_id: item for item in self.accounts}
        category_by_id = {item.source_id: item for item in self.categories}
        transaction_by_id = {item.source_id: item for item in self.transactions}
        self._validate_members()
        self._validate_active_names()
        self._validate_timestamps()

        for transaction in self.transactions:
            if transaction.account_source_id not in account_by_id:
                raise ValueError("transaction references an unknown account")
            if (
                transaction.category_source_id
                and transaction.category_source_id not in category_by_id
            ):
                raise ValueError("transaction references an unknown category")
            if (
                transaction.paid_by_member_source_id
                and transaction.paid_by_member_source_id not in member_by_id
            ):
                raise ValueError("transaction references an unknown payer")
            if (
                transaction.direction not in {"expense", "income"}
                and transaction.paid_by_member_source_id
            ):
                raise ValueError("non-cashflow transaction cannot reference a payer")

        split_totals: defaultdict[UUID, int] = defaultdict(int)
        split_keys: set[tuple[UUID, UUID]] = set()
        for split in self.splits:
            if (
                split.transaction_source_id not in transaction_by_id
                or split.member_source_id not in member_by_id
            ):
                raise ValueError("split references an unknown transaction or member")
            key = (split.transaction_source_id, split.member_source_id)
            if key in split_keys:
                raise ValueError("bundle contains a duplicate transaction split")
            split_keys.add(key)
            split_totals[split.transaction_source_id] += split.amount_paise

        for transaction in self.transactions:
            total = split_totals[transaction.source_id]
            if transaction.direction in {"expense", "income"}:
                if total != transaction.amount_paise:
                    raise ValueError("cashflow transaction splits must equal its amount")
            elif total:
                raise ValueError("non-cashflow transaction cannot contain splits")

        linked_transactions: set[UUID] = set()
        for transfer in self.transfers:
            if (
                transfer.out_transaction_source_id not in transaction_by_id
                or transfer.in_transaction_source_id not in transaction_by_id
            ):
                raise ValueError("transfer references an unknown transaction")
            if transfer.out_transaction_source_id == transfer.in_transaction_source_id:
                raise ValueError("transfer transactions must be different")
            if (
                transfer.out_transaction_source_id in linked_transactions
                or transfer.in_transaction_source_id in linked_transactions
            ):
                raise ValueError("transfer transaction is linked more than once")
            linked_transactions.update(
                {
                    transfer.out_transaction_source_id,
                    transfer.in_transaction_source_id,
                }
            )
            outgoing = transaction_by_id[transfer.out_transaction_source_id]
            incoming = transaction_by_id[transfer.in_transaction_source_id]
            if outgoing.direction != "transfer_out" or incoming.direction != "transfer_in":
                raise ValueError("transfer link directions are invalid")
            if outgoing.account_source_id == incoming.account_source_id:
                raise ValueError("transfer accounts must be different")
            if (
                outgoing.amount_paise != incoming.amount_paise
                or outgoing.currency != incoming.currency
                or outgoing.status != incoming.status
            ):
                raise ValueError("linked transfer facts must match")

        settlement_transactions: set[UUID] = set()
        for settlement in self.settlements:
            if (
                settlement.payer_member_source_id not in member_by_id
                or settlement.payee_member_source_id not in member_by_id
            ):
                raise ValueError("settlement references an unknown member")
            if settlement.payer_member_source_id == settlement.payee_member_source_id:
                raise ValueError("settlement members must be different")
            linked_values = (
                settlement.account_source_id,
                settlement.transaction_source_id,
                settlement.account_direction,
            )
            if any(value is not None for value in linked_values) and any(
                value is None for value in linked_values
            ):
                raise ValueError("settlement account linkage must be complete")
            if (
                settlement.account_source_id is None
                or settlement.transaction_source_id is None
            ):
                continue
            if settlement.account_source_id not in account_by_id:
                raise ValueError("settlement references an unknown account")
            if settlement.transaction_source_id not in transaction_by_id:
                raise ValueError("settlement references an unknown transaction")
            if settlement.transaction_source_id in settlement_transactions:
                raise ValueError("settlement transaction is linked more than once")
            settlement_transactions.add(settlement.transaction_source_id)
            transaction = transaction_by_id[settlement.transaction_source_id]
            if (
                transaction.direction != settlement.account_direction
                or transaction.account_source_id != settlement.account_source_id
                or transaction.amount_paise != settlement.amount_paise
                or transaction.currency != settlement.currency
                or transaction.occurred_at != settlement.settled_at
            ):
                raise ValueError("linked settlement facts must match")

        for rule in self.merchant_rules:
            if rule.category_source_id not in category_by_id:
                raise ValueError("merchant rule references an unknown category")
            if rule.account_source_id and rule.account_source_id not in account_by_id:
                raise ValueError("merchant rule references an unknown account")
        return self

    def _validate_unique_source_ids(self) -> None:
        collections: tuple[tuple[str, list[Any]], ...] = (
            ("member", self.members),
            ("account", self.accounts),
            ("category", self.categories),
            ("transaction", self.transactions),
            ("transfer", self.transfers),
            ("settlement", self.settlements),
            ("merchant rule", self.merchant_rules),
            ("audit event", self.audit_events),
        )
        for label, items in collections:
            source_ids = [item.source_id for item in items]
            if len(source_ids) != len(set(source_ids)):
                raise ValueError(f"bundle contains duplicate {label} source IDs")

    def _validate_members(self) -> None:
        owners = [
            item
            for item in self.members
            if item.member_type == "user" and item.role == "owner"
        ]
        if len(owners) != 1 or not owners[0].is_active:
            raise ValueError("bundle must contain exactly one active owner")
        if owners[0].display_name != self.profile.display_name:
            raise ValueError("owner and profile display names must match")
        if any(
            item not in owners
            and (item.member_type != "participant" or item.role != "member")
            for item in self.members
        ):
            raise ValueError("bundle supports only one owner and participant members")

    def _validate_active_names(self) -> None:
        groups: tuple[tuple[str, list[str]], ...] = (
            (
                "account",
                [item.name for item in self.accounts if not item.is_archived],
            ),
            (
                "category",
                [item.name for item in self.categories if not item.is_archived],
            ),
            (
                "member",
                [item.display_name for item in self.members if item.is_active],
            ),
        )
        for label, names in groups:
            normalized = [" ".join(name.casefold().split()) for name in names]
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"bundle contains duplicate active {label} names")

    def _validate_timestamps(self) -> None:
        timestamps: list[datetime] = [self.exported_at]
        timestamps.extend(account.created_at for account in self.accounts)
        timestamps.extend(category.created_at for category in self.categories)
        for transaction in self.transactions:
            timestamps.extend((transaction.occurred_at, transaction.created_at))
            if transaction.voided_at:
                timestamps.append(transaction.voided_at)
        timestamps.extend(transfer.created_at for transfer in self.transfers)
        for settlement in self.settlements:
            timestamps.extend((settlement.settled_at, settlement.created_at))
        timestamps.extend(rule.created_at for rule in self.merchant_rules)
        timestamps.extend(event.occurred_at for event in self.audit_events)
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("recovery timestamps must include a timezone")

    def summary(self) -> dict[str, int | str]:
        canonical = json.dumps(
            self.model_dump(mode="json", exclude_none=False),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return {
            "sha256": sha256(canonical.encode()).hexdigest(),
            "members": len(self.members),
            "accounts": len(self.accounts),
            "categories": len(self.categories),
            "transactions": len(self.transactions),
            "splits": len(self.splits),
            "transfers": len(self.transfers),
            "settlements": len(self.settlements),
            "merchant_rules": len(self.merchant_rules),
            "audit_events": len(self.audit_events),
        }

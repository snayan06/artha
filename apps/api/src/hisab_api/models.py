from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AccountKind(StrEnum):
    BANK = "bank"
    CASH = "cash"
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"


class TransactionKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    SETTLEMENT = "settlement"


class SettlementDirection(StrEnum):
    RECEIVED = "received"
    PAID = "paid"


class MerchantMatchType(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[AccountKind] = mapped_column(Enum(AccountKind))
    opening_balance_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    credit_limit_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    statement_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    entries: Mapped[list[LedgerEntry]] = relationship(back_populates="account")

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_account_user_name"),)


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_member_user_name"),)


class MerchantRule(Base):
    __tablename__ = "merchant_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    match_type: Mapped[MerchantMatchType] = mapped_column(Enum(MerchantMatchType), index=True)
    merchant_pattern: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(80))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        Index(
            "uq_merchant_rule_scope",
            "user_id",
            "match_type",
            "merchant_pattern",
            func.coalesce(account_id, 0),
            unique=True,
        ),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[TransactionKind] = mapped_column(Enum(TransactionKind), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    personal_share_paise: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(240))
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    paid_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("household_members.id"), nullable=True
    )
    settlement_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("household_members.id"), nullable=True
    )
    settlement_direction: Mapped[SettlementDirection | None] = mapped_column(
        Enum(SettlementDirection), nullable=True
    )
    source_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    destination_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    entries: Mapped[list[LedgerEntry]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    splits: Mapped[list[TransactionSplit]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("household_members.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)

    transaction: Mapped[Transaction] = relationship(back_populates="splits")

    __table_args__ = (
        UniqueConstraint("transaction_id", "member_id", name="uq_split_transaction_member"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    delta_paise: Mapped[int] = mapped_column(BigInteger)

    transaction: Mapped[Transaction] = relationship(back_populates="entries")
    account: Mapped[Account] = relationship(back_populates="entries")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),)

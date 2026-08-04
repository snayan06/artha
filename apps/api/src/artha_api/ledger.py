from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Account,
    HouseholdMember,
    LedgerEntry,
    SettlementDirection,
    Transaction,
    TransactionKind,
    TransactionSplit,
)
from .schemas import MemberBalanceDelta, TransactionDraft, TransactionRead


@dataclass(frozen=True)
class EntrySpec:
    account_id: int
    delta_paise: int


def entry_specs(draft: TransactionDraft) -> list[EntrySpec]:
    account_id = draft.source_account_id
    if account_id is None:
        raise ValueError("source account is required")

    if draft.kind is TransactionKind.EXPENSE:
        if draft.paid_by_member_id is not None:
            return []
        return [EntrySpec(account_id, -draft.amount_paise)]
    if draft.kind is TransactionKind.INCOME:
        return [EntrySpec(account_id, draft.amount_paise)]
    if draft.kind is TransactionKind.TRANSFER:
        if draft.destination_account_id is None:
            raise ValueError("destination account is required")
        return [
            EntrySpec(account_id, -draft.amount_paise),
            EntrySpec(draft.destination_account_id, draft.amount_paise),
        ]
    if draft.settlement_direction is SettlementDirection.RECEIVED:
        return [EntrySpec(account_id, draft.amount_paise)]
    return [EntrySpec(account_id, -draft.amount_paise)]


def member_deltas(
    transaction: Transaction | TransactionDraft,
    splits: Sequence[TransactionSplit],
) -> list[MemberBalanceDelta]:
    if transaction.kind is TransactionKind.EXPENSE:
        if transaction.paid_by_member_id is None:
            return [
                MemberBalanceDelta(member_id=split.member_id, amount_paise=split.amount_paise)
                for split in splits
            ]
        return [
            MemberBalanceDelta(
                member_id=transaction.paid_by_member_id,
                amount_paise=-transaction.personal_share_paise,
            )
        ]
    if (
        transaction.kind is TransactionKind.SETTLEMENT
        and transaction.settlement_member_id is not None
    ):
        amount = (
            -transaction.amount_paise
            if transaction.settlement_direction is SettlementDirection.RECEIVED
            else transaction.amount_paise
        )
        return [
            MemberBalanceDelta(
                member_id=transaction.settlement_member_id,
                amount_paise=amount,
            )
        ]
    return []


async def verify_accounts(
    session: AsyncSession, account_ids: Sequence[int | None], user_id: str
) -> None:
    ids = {account_id for account_id in account_ids if account_id is not None}
    if not ids:
        return
    result = await session.scalars(
        select(Account.id).where(
            Account.user_id == user_id,
            Account.id.in_(ids),
            Account.is_archived.is_(False),
        )
    )
    found = set(result.all())
    if found != ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "account not found or archived")


async def verify_members(
    session: AsyncSession, member_ids: Sequence[int | None], user_id: str
) -> None:
    ids = {member_id for member_id in member_ids if member_id is not None}
    if not ids:
        return
    result = await session.scalars(
        select(HouseholdMember.id).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.id.in_(ids),
            HouseholdMember.is_archived.is_(False),
        )
    )
    if set(result.all()) != ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "household member not found or archived")


async def create_transaction(
    session: AsyncSession, draft: TransactionDraft, user_id: str
) -> Transaction:
    await verify_accounts(
        session, [draft.source_account_id, draft.destination_account_id], user_id=user_id
    )
    await verify_members(
        session,
        [
            draft.paid_by_member_id,
            draft.settlement_member_id,
            *(split.member_id for split in draft.splits),
        ],
        user_id=user_id,
    )
    values = draft.model_dump(exclude={"occurred_at", "splits"})
    occurred_at = draft.occurred_at
    transaction = Transaction(user_id=user_id, **values)
    if occurred_at is not None:
        transaction.occurred_at = occurred_at
    session.add(transaction)
    await session.flush()
    session.add_all(
        LedgerEntry(
            transaction_id=transaction.id,
            account_id=spec.account_id,
            delta_paise=spec.delta_paise,
        )
        for spec in entry_specs(draft)
    )
    session.add_all(
        TransactionSplit(
            transaction_id=transaction.id,
            member_id=split.member_id,
            amount_paise=split.amount_paise,
        )
        for split in draft.splits
    )
    await session.flush()
    return transaction


async def replace_entries(
    session: AsyncSession, transaction: Transaction, draft: TransactionDraft
) -> None:
    await verify_accounts(
        session,
        [draft.source_account_id, draft.destination_account_id],
        user_id=transaction.user_id,
    )
    await verify_members(
        session,
        [
            draft.paid_by_member_id,
            draft.settlement_member_id,
            *(split.member_id for split in draft.splits),
        ],
        user_id=transaction.user_id,
    )
    await session.execute(delete(LedgerEntry).where(LedgerEntry.transaction_id == transaction.id))
    await session.execute(
        delete(TransactionSplit).where(TransactionSplit.transaction_id == transaction.id)
    )
    for field, value in draft.model_dump(exclude={"splits"}).items():
        if field == "occurred_at" and value is None:
            continue
        setattr(transaction, field, value)
    session.add_all(
        LedgerEntry(
            transaction_id=transaction.id,
            account_id=spec.account_id,
            delta_paise=spec.delta_paise,
        )
        for spec in entry_specs(draft)
    )
    session.add_all(
        TransactionSplit(
            transaction_id=transaction.id,
            member_id=split.member_id,
            amount_paise=split.amount_paise,
        )
        for split in draft.splits
    )
    await session.flush()


async def transaction_to_read(session: AsyncSession, transaction: Transaction) -> TransactionRead:
    movement = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta_paise), 0)).where(
            LedgerEntry.transaction_id == transaction.id
        )
    )
    splits = list(
        (
            await session.scalars(
                select(TransactionSplit)
                .where(TransactionSplit.transaction_id == transaction.id)
                .order_by(TransactionSplit.id)
            )
        ).all()
    )
    return TransactionRead.model_validate(
        {
            **{
                column.name: getattr(transaction, column.name)
                for column in Transaction.__table__.columns
            },
            "splits": splits,
            "account_delta_paise": int(movement or 0),
            "member_balance_deltas": member_deltas(transaction, splits),
        }
    )


async def transactions_to_read(
    session: AsyncSession, transactions: Sequence[Transaction]
) -> list[TransactionRead]:
    return [await transaction_to_read(session, transaction) for transaction in transactions]

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantEvidence,
    AssistantEvidenceTransaction,
    AssistantFinancialContext,
    AssistantIntent,
    AssistantStatus,
    AssistantUnavailableError,
    ContextCategory,
    ContextMemberBalance,
    ContextMonth,
    ContextTransaction,
    LocalFinancialAssistant,
    TagSuggestionRequest,
    TagSuggestionResponse,
)
from .auth import AuthDependency
from .database import get_session
from .routes import dashboard
from .schemas import DashboardResponse

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_assistant() -> LocalFinancialAssistant:
    return LocalFinancialAssistant()


AssistantDependency = Annotated[LocalFinancialAssistant, Depends(get_assistant)]


def _safe_label(value: str | None) -> str:
    printable = "".join(character for character in (value or "") if character.isprintable())
    return printable.strip()[:40] or "Uncategorized"


async def compact_financial_context(
    session: AsyncSession,
    auth: AuthDependency,
    summary: DashboardResponse | None = None,
) -> AssistantFinancialContext:
    # The model receives only server-derived aggregates and a bounded projection.
    # Merchant text, notes, account identifiers, user IDs and raw rows are excluded.
    summary = summary or await dashboard(session, auth)
    return AssistantFinancialContext(
        total_balance_paise=summary.total_balance_paise,
        current_month_spend_paise=summary.spend_paise,
        current_month_income_paise=summary.income_paise,
        member_balances=[
            ContextMemberBalance(
                member_name=_safe_label(item.member_name),
                balance_paise=item.balance_paise,
            )
            for item in summary.member_balances[:20]
        ],
        top_categories=[
            ContextCategory(
                category=_safe_label(item.category),
                amount_paise=item.amount_paise,
            )
            for item in summary.spend_by_category[:5]
        ],
        monthly=[
            ContextMonth(
                month=_safe_label(item.month)[:12],
                income_paise=item.income_paise,
                spend_paise=item.spend_paise,
            )
            for item in summary.monthly[-6:]
        ],
        recent_transactions=[
            ContextTransaction(
                occurred_on=item.occurred_at.date().isoformat(),
                kind=item.kind.value,
                personal_share_paise=item.personal_share_paise,
                category=_safe_label(item.category),
            )
            for item in summary.recent_transactions[:8]
            if item.kind.value in {"expense", "income", "transfer", "settlement"}
        ],
    )


def local_assistant_evidence(
    intent: AssistantIntent,
    summary: DashboardResponse,
) -> AssistantEvidence:
    """Build safe source references for the local/demo API response contract.

    Local aggregates are calculated across the full SQLite ledger, while the
    dashboard intentionally returns only ten recent rows. The basis therefore
    describes these rows as references instead of claiming they are the full
    aggregate source set.
    """
    now = datetime.now(UTC)
    current_month_key = now.strftime("%Y-%m")
    six_month_keys = {
        f"{year:04d}-{month_index + 1:02d}"
        for months_back in range(6)
        for year, month_index in [divmod(now.year * 12 + now.month - 1 - months_back, 12)]
    }
    rows = summary.recent_transactions[:8]
    if intent is AssistantIntent.SPENDING:
        period = "Current month"
        rows = [
            row
            for row in rows
            if row.kind.value == "expense"
            and row.occurred_at.strftime("%Y-%m") == current_month_key
        ]
    elif intent is AssistantIntent.INCOME:
        period = "Current month"
        rows = [
            row
            for row in rows
            if row.kind.value == "income" and row.occurred_at.strftime("%Y-%m") == current_month_key
        ]
    elif intent is AssistantIntent.CASHFLOW:
        period = "Last 6 calendar months"
        rows = [
            row
            for row in rows
            if row.kind.value in {"expense", "income"}
            and row.occurred_at.strftime("%Y-%m") in six_month_keys
        ]
    elif intent is AssistantIntent.SHARED:
        period = "Current household position"
        rows = [row for row in rows if row.kind.value == "settlement" or bool(row.splits)]
    elif intent is AssistantIntent.TRANSACTIONS:
        period = "Latest ledger activity"
    elif intent is AssistantIntent.SUMMARY:
        period = "Current balances and current month"
        rows = [
            row
            for row in rows
            if row.kind.value in {"expense", "income"}
            and row.occurred_at.strftime("%Y-%m") == current_month_key
        ]
    else:
        return AssistantEvidence(
            period="No ledger range selected",
            basis="No ledger calculation was performed.",
            source_count=0,
            capped=False,
            transactions=[],
        )

    return AssistantEvidence(
        period=period,
        basis=(
            "Server-calculated ledger totals; source count covers the recent "
            "matching entries available as references."
        ),
        source_count=len(rows),
        capped=False,
        transactions=[
            AssistantEvidenceTransaction(
                id=str(row.id),
                occurred_on=row.occurred_at.date().isoformat(),
                label=_safe_label(row.description),
                kind=row.kind.value,
                amount_paise=(
                    row.personal_share_paise
                    if row.kind.value in {"expense", "income"}
                    else row.amount_paise
                ),
            )
            for row in rows
        ],
    )


@router.get("/status", response_model=AssistantStatus)
async def assistant_status(assistant: AssistantDependency) -> AssistantStatus:
    return await assistant.status()


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    payload: AssistantChatRequest,
    session: SessionDependency,
    auth: AuthDependency,
    assistant: AssistantDependency,
) -> AssistantChatResponse:
    summary = await dashboard(session, auth)
    context = await compact_financial_context(session, auth, summary)
    try:
        response = await assistant.chat(payload.message, context)
        return response.model_copy(
            update={"evidence": local_assistant_evidence(response.result.intent, summary)}
        )
    except AssistantUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI is temporarily unavailable; the ledger was not changed.",
        ) from error


@router.post("/tag-suggestion", response_model=TagSuggestionResponse)
async def assistant_tag_suggestion(
    payload: TagSuggestionRequest,
    auth: AuthDependency,
    assistant: AssistantDependency,
) -> TagSuggestionResponse:
    # Authentication gates access, but the model receives no identity and this
    # endpoint intentionally has no DB session or persistence capability.
    del auth
    try:
        return await assistant.suggest_tag(payload)
    except AssistantUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ("AI category suggestion is temporarily unavailable; the ledger was not changed."),
        ) from error

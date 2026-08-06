from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantFinancialContext,
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

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_assistant() -> LocalFinancialAssistant:
    return LocalFinancialAssistant()


AssistantDependency = Annotated[LocalFinancialAssistant, Depends(get_assistant)]


def _safe_label(value: str | None) -> str:
    printable = "".join(character for character in (value or "") if character.isprintable())
    return printable.strip()[:40] or "Uncategorized"


async def compact_financial_context(
    session: AsyncSession, auth: AuthDependency
) -> AssistantFinancialContext:
    # The model receives only server-derived aggregates and a bounded projection.
    # Merchant text, notes, account identifiers, user IDs and raw rows are excluded.
    summary = await dashboard(session, auth)
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
    context = await compact_financial_context(session, auth)
    try:
        return await assistant.chat(payload.message, context)
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
            (
                "AI category suggestion is temporarily unavailable; "
                "the ledger was not changed."
            ),
        ) from error

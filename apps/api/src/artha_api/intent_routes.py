from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from .assistant import AssistantUnavailableError, LocalFinancialAssistant
from .auth import AuthDependency
from .intent_router import IntentRouteRequest, IntentRouteResponse

router = APIRouter(prefix="/api/v1/intents", tags=["assistant"])


def get_intent_assistant() -> LocalFinancialAssistant:
    return LocalFinancialAssistant()


IntentAssistantDependency = Annotated[
    LocalFinancialAssistant, Depends(get_intent_assistant)
]


@router.post("/route", response_model=IntentRouteResponse)
async def route_intent(
    payload: IntentRouteRequest,
    auth: AuthDependency,
    assistant: IntentAssistantDependency,
) -> IntentRouteResponse:
    del auth
    try:
        return await assistant.route_intent(payload.message)
    except AssistantUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI routing is temporarily unavailable; nothing was saved.",
        ) from error


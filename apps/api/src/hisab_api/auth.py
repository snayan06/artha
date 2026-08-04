from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user_id: str


async def get_auth_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if not request.app.state.is_production:
        return AuthContext(user_id=request.app.state.demo_user_id)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Production authentication is not connected",
    )


AuthDependency = Annotated[AuthContext, Depends(get_auth_context)]

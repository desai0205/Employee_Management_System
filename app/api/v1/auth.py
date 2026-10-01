"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import Caller, get_auth_service, get_caller, get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import StatusMessage
from app.services.auth import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    caller: Annotated[Caller, Depends(get_caller)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    return await service.login(
        str(payload.email),
        payload.password,
        ip_address=caller.ip_address,
        user_agent=caller.user_agent,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    caller: Annotated[Caller, Depends(get_caller)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    return await service.refresh(
        payload.refresh_token,
        ip_address=caller.ip_address,
        user_agent=caller.user_agent,
    )


@router.post("/logout", response_model=StatusMessage)
async def logout(
    payload: LogoutRequest,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> StatusMessage:
    await service.logout(actor, payload.refresh_token, ip_address=caller.ip_address)
    return StatusMessage(status="ok")


@router.get("/me", response_model=MeResponse)
async def me(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> MeResponse:
    return await service.me(actor)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    caller: Annotated[Caller, Depends(get_caller)],
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await service.change_password(
        actor,
        payload.current_password,
        payload.new_password,
        ip_address=caller.ip_address,
    )

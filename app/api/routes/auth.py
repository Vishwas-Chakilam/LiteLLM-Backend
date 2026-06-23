from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserProfile

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest) -> AuthResponse:
    from fastapi import HTTPException
    from app.middleware.auth import get_auth_service

    try:
        return get_auth_service().signup(body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    from fastapi import HTTPException
    from app.middleware.auth import get_auth_service

    try:
        return get_auth_service().login(body)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=UserProfile)
async def me(
    user: Annotated[UserProfile | None, Depends(get_current_user)],
) -> UserProfile:
    from fastapi import HTTPException

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

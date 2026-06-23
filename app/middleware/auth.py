from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.schemas.auth import UserProfile, UserRole
from app.services.supabase.auth_service import AuthService

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def get_auth_service() -> AuthService:
    return AuthService()


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserProfile | None:
    settings = get_settings()
    if not settings.auth_required:
        return None

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = auth_service.get_user_by_token(credentials.credentials)
        request.state.user = user
        return user
    except Exception as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def require_roles(*roles: UserRole):
    async def _checker(
        user: Annotated[UserProfile | None, Depends(get_current_user)],
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> UserProfile:
        settings = get_settings()
        if not settings.auth_required:
            return user or UserProfile(
                id="dev-admin",
                email="dev@localhost",
                full_name="Dev Admin",
                role=UserRole.ADMIN,
            )
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        auth_service.validate_role(user, set(roles))
        return user

    return _checker


require_admin = require_roles(UserRole.ADMIN)

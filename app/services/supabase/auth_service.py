from __future__ import annotations

import logging
from typing import Any

from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest, UserProfile, UserRole
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)

ALLOWED_SELF_SIGNUP_ROLES = {UserRole.PATIENT, UserRole.SUPPORT}


class AuthService:
    def __init__(self) -> None:
        self._factory = get_supabase_factory()

    def signup(self, request: SignupRequest) -> AuthResponse:
        if request.role not in ALLOWED_SELF_SIGNUP_ROLES:
            raise PermissionError(f"Self-signup not allowed for role: {request.role}")

        client = self._factory.service_client()
        result = client.auth.sign_up(
            {
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": {
                        "full_name": request.full_name,
                        "role": request.role.value,
                    }
                },
            }
        )
        if not result.session:
            raise ValueError("Signup succeeded but no session returned. Check email confirmation settings.")

        user = self._to_profile(result.user.id, request.email, request)
        self._update_profile(result.user.id, request)
        return AuthResponse(
            access_token=result.session.access_token,
            refresh_token=result.session.refresh_token,
            expires_in=result.session.expires_in,
            user=user,
        )

    def login(self, request: LoginRequest) -> AuthResponse:
        client = self._factory.service_client()
        result = client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
        if not result.session or not result.user:
            raise ValueError("Invalid credentials")

        profile = self.get_user(str(result.user.id))
        return AuthResponse(
            access_token=result.session.access_token,
            refresh_token=result.session.refresh_token,
            expires_in=result.session.expires_in,
            user=profile,
        )

    def get_user(self, user_id: str) -> UserProfile:
        client = self._factory.service_client()
        row = (
            client.table("users")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        data = row.data
        return UserProfile(
            id=data["id"],
            email=data["email"],
            full_name=data.get("full_name"),
            role=UserRole(data["role"]),
            phone=data.get("phone"),
            organization=data.get("organization"),
            created_at=data.get("created_at"),
        )

    def get_user_by_token(self, access_token: str) -> UserProfile:
        client = self._factory.service_client()
        result = client.auth.get_user(access_token)
        if not result or not result.user:
            raise ValueError("Invalid or expired token")
        return self.get_user(str(result.user.id))

    def validate_role(self, user: UserProfile, allowed_roles: set[UserRole]) -> None:
        if user.role not in allowed_roles:
            raise PermissionError(f"Role '{user.role}' not authorized for this action")

    def _update_profile(self, user_id: str, request: SignupRequest) -> None:
        client = self._factory.service_client()
        updates: dict[str, Any] = {}
        if request.phone:
            updates["phone"] = request.phone
        if request.organization:
            updates["organization"] = request.organization
        if updates:
            client.table("users").update(updates).eq("id", user_id).execute()

    def _to_profile(self, user_id: str, email: str, request: SignupRequest) -> UserProfile:
        return UserProfile(
            id=str(user_id),
            email=email,
            full_name=request.full_name,
            role=request.role,
            phone=request.phone,
            organization=request.organization,
        )

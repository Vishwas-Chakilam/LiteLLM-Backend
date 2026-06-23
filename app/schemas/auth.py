from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"
    INSURANCE_AGENT = "insurance_agent"
    SUPPORT = "support"


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    role: UserRole = UserRole.PATIENT
    phone: str | None = None
    organization: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user: UserProfile


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: UserRole
    phone: str | None = None
    organization: str | None = None
    created_at: datetime | None = None


class TokenPayload(BaseModel):
    sub: str
    email: str | None = None
    role: str | None = None
    exp: int | None = None

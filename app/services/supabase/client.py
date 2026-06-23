from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.config import get_settings

logger = logging.getLogger(__name__)


class SupabaseClientFactory:
    """Factory for Supabase clients (service role vs user-scoped)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.supabase_url
        self._service_key = settings.supabase_service_role_key
        self._anon_key = settings.supabase_anon_key
        self._service_client: Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self._url and self._service_key and self._url.startswith("http"))

    def service_client(self) -> Client:
        if not self.configured:
            raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        if self._service_client is None:
            self._service_client = create_client(self._url, self._service_key)
        return self._service_client

    def user_client(self, access_token: str) -> Client:
        if not self._url or not self._anon_key:
            raise RuntimeError("Supabase anon key not configured.")
        client = create_client(self._url, self._anon_key)
        client.postgrest.auth(access_token)
        return client


@lru_cache
def get_supabase_factory() -> SupabaseClientFactory:
    return SupabaseClientFactory()


def row_to_dict(row: dict[str, Any] | None) -> dict[str, Any]:
    return dict(row) if row else {}

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.supabase.client import get_supabase_factory

logger = logging.getLogger(__name__)


def _normalize_insurer(insurer: str) -> str:
    return insurer.lower().strip().replace(" ", "_").replace("-", "_")


class HospitalDataService:
    """Reads hospital master data from Supabase (Option 1) with JSON fallback for dev/tests."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._factory = get_supabase_factory()
        self._fallback = self._load_fallback()
        self._hospital_slug = self._settings.hospital_slug

    def _load_fallback(self) -> dict[str, Any]:
        path = Path(self._settings.hospital_data_file)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _client(self):
        return self._factory.service_client()

    def _hospital_id_from_slug(self, slug: str) -> str | None:
        if self._factory.configured:
            try:
                row = (
                    self._client()
                    .table("hospitals")
                    .select("id")
                    .eq("slug", slug)
                    .eq("is_active", True)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    return row.data[0]["id"]
            except Exception as exc:
                logger.warning("Hospital lookup failed: %s", exc)
        fb = self._fallback.get("hospital", {})
        return fb.get("id") if fb.get("slug") == slug else fb.get("id")

    def get_hospital_info(self, slug: str | None = None) -> dict[str, Any]:
        slug = slug or self._hospital_slug
        if self._factory.configured:
            try:
                row = (
                    self._client()
                    .table("hospitals")
                    .select("*")
                    .eq("slug", slug)
                    .eq("is_active", True)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    return row.data[0]
            except Exception as exc:
                logger.warning("get_hospital_info supabase failed: %s", exc)
        hospital = self._fallback.get("hospital", {})
        if hospital.get("slug") == slug or slug == self._hospital_slug:
            return hospital
        return {}

    def get_accepted_insurers(self, slug: str | None = None) -> list[dict[str, Any]]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        if self._factory.configured and hospital_id:
            try:
                rows = (
                    self._client()
                    .table("hospital_insurance_plans")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .execute()
                )
                if rows.data:
                    return rows.data
            except Exception as exc:
                logger.warning("get_accepted_insurers failed: %s", exc)
        return self._fallback.get("insurance_plans", [])

    def check_insurance_accepted(self, insurer: str, slug: str | None = None) -> dict[str, Any]:
        if not insurer:
            return {
                "insurer": "",
                "hospital": self.get_hospital_info(slug).get("name", ""),
                "accepted": False,
                "in_network": False,
                "reason": "No insurer specified on patient profile or request.",
                "matched_plan": None,
            }
        norm = _normalize_insurer(insurer)
        aliases = {
            "aetna": ["aetna"],
            "united": ["united", "unitedhealthcare", "uhc"],
            "cigna": ["cigna"],
            "bcbs": ["bcbs", "blue_cross", "bluecross", "blue_shield"],
            "medicare": ["medicare"],
            "medicaid": ["medicaid"],
            "humana": ["humana"],
        }
        hospital = self.get_hospital_info(slug)
        plans = self.get_accepted_insurers(slug)

        matched = None
        for plan in plans:
            pid = _normalize_insurer(plan.get("insurer_id", ""))
            pname = _normalize_insurer(plan.get("insurer_name", ""))
            if norm == pid or norm in pname or norm in aliases.get(pid, [pid]):
                matched = plan
                break
            for alias_list in aliases.values():
                if norm in alias_list and (pid in alias_list or any(a in pname for a in alias_list)):
                    matched = plan
                    break

        if not matched:
            # fuzzy: insurer string contained in name
            for plan in plans:
                if norm in _normalize_insurer(plan.get("insurer_name", "")):
                    matched = plan
                    break

        return {
            "insurer": insurer,
            "hospital": hospital.get("name", "City General Hospital"),
            "hospital_slug": hospital.get("slug", slug),
            "accepted": matched is not None and matched.get("in_network", False),
            "in_network": matched.get("in_network", False) if matched else False,
            "matched_plan": matched,
            "all_accepted_insurers": [
                {"insurer_id": p.get("insurer_id"), "insurer_name": p.get("insurer_name"), "in_network": p.get("in_network")}
                for p in plans
            ],
            "reason": (
                f"{matched.get('insurer_name')} is in-network at {hospital.get('name')}."
                if matched and matched.get("in_network")
                else f"{insurer} is not in-network at {hospital.get('name')}."
                if matched
                else f"No matching plan found for '{insurer}'."
            ),
        }

    def list_departments(self, slug: str | None = None) -> list[dict[str, Any]]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        if self._factory.configured and hospital_id:
            try:
                rows = (
                    self._client()
                    .table("hospital_departments")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .execute()
                )
                if rows.data:
                    return rows.data
            except Exception as exc:
                logger.warning("list_departments failed: %s", exc)
        return self._fallback.get("departments", [])

    def list_providers(self, specialty: str | None = None, slug: str | None = None) -> list[dict[str, Any]]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        if self._factory.configured and hospital_id:
            try:
                q = self._client().table("hospital_providers").select("*").eq("hospital_id", hospital_id)
                if specialty:
                    q = q.ilike("specialty", f"%{specialty}%")
                rows = q.execute()
                if rows.data:
                    return rows.data
            except Exception as exc:
                logger.warning("list_providers failed: %s", exc)
        providers = self._fallback.get("providers", [])
        if specialty:
            spec_lower = specialty.lower()
            providers = [p for p in providers if spec_lower in p.get("specialty", "").lower()]
        return providers

    def list_services(self, slug: str | None = None) -> list[dict[str, Any]]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        if self._factory.configured and hospital_id:
            try:
                rows = (
                    self._client()
                    .table("hospital_services")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .execute()
                )
                if rows.data:
                    return rows.data
            except Exception as exc:
                logger.warning("list_services failed: %s", exc)
        return self._fallback.get("services", [])

    def get_hospital_payer_rules(
        self, insurer: str, procedure_type: str = "general", slug: str | None = None
    ) -> dict[str, Any]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        norm = _normalize_insurer(insurer)
        if self._factory.configured and hospital_id and insurer:
            try:
                rows = (
                    self._client()
                    .table("hospital_payer_rules")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .eq("procedure_type", procedure_type)
                    .execute()
                )
                for row in rows.data or []:
                    if _normalize_insurer(row.get("insurer_id", "")) == norm:
                        return {"insurer": insurer, "procedure_type": procedure_type, **row.get("rules", {})}
                # fallback procedure type
                rows = (
                    self._client()
                    .table("hospital_payer_rules")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .eq("insurer_id", norm)
                    .eq("procedure_type", "general")
                    .limit(1)
                    .execute()
                )
                if rows.data:
                    return {"insurer": insurer, "procedure_type": "general", **rows.data[0].get("rules", {})}
            except Exception as exc:
                logger.warning("get_hospital_payer_rules failed: %s", exc)
        for rule in self._fallback.get("payer_rules", []):
            if _normalize_insurer(rule.get("insurer_id", "")) == norm and rule.get("procedure_type") == procedure_type:
                return {"insurer": insurer, "procedure_type": procedure_type, **rule.get("rules", {})}
        return {"insurer": insurer, "procedure_type": procedure_type, "requires_clinical_notes": True}

    def get_lab_reference_range(self, marker: str, slug: str | None = None) -> dict[str, Any]:
        slug = slug or self._hospital_slug
        hospital_id = self._hospital_id_from_slug(slug)
        marker_lower = marker.lower()
        if self._factory.configured and hospital_id:
            try:
                row = (
                    self._client()
                    .table("hospital_lab_reference_ranges")
                    .select("*")
                    .eq("hospital_id", hospital_id)
                    .ilike("marker", marker_lower)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    return row.data[0]
            except Exception as exc:
                logger.warning("get_lab_reference_range failed: %s", exc)
        for r in self._fallback.get("lab_ranges", []):
            if r.get("marker", "").lower() == marker_lower:
                return r
        return {"marker": marker, "low": 0, "high": 100, "unit": "units", "source": "default"}

    def get_context_snapshot(self, slug: str | None = None) -> dict[str, Any]:
        """Full hospital bundle injected into agent workflows."""
        slug = slug or self._hospital_slug
        hospital = self.get_hospital_info(slug)
        return {
            "hospital_id": hospital.get("id"),
            "hospital_slug": hospital.get("slug", slug),
            "hospital_name": hospital.get("name"),
            "hospital": hospital,
            "accepted_insurers": self.get_accepted_insurers(slug),
            "departments": self.list_departments(slug),
        }

    def get_demo_patients(self) -> list[dict[str, Any]]:
        hospital = self.get_hospital_info()
        meta = hospital.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        demos = meta.get("demo_patients")
        if demos:
            return demos
        return self._fallback.get("demo_patients", [])


@lru_cache
def get_hospital_service() -> HospitalDataService:
    return HospitalDataService()

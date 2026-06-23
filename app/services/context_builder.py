from __future__ import annotations

from typing import Any

from app.schemas.auth import UserProfile
from app.services.hospital_data_service import get_hospital_service
from app.services.supabase.client import get_supabase_factory
from app.services.supabase.patient_service import PatientService


def resolve_insurer(ctx: dict[str, Any]) -> str:
    """Resolve insurer from patient context fields."""
    if ctx.get("insurer"):
        return str(ctx["insurer"])
    if ctx.get("insurance_provider"):
        return str(ctx["insurance_provider"])
    profile = ctx.get("patient_profile") or {}
    if isinstance(profile, dict) and profile.get("insurance_provider"):
        return str(profile["insurance_provider"])
    return ""


def build_agent_context(
    user: UserProfile | None = None,
    extra: dict[str, Any] | None = None,
    demo_patient_index: int | None = None,
) -> dict[str, Any]:
    """Merge patient profile, hospital master data, and request extras for agents."""
    hospital_svc = get_hospital_service()
    ctx: dict[str, Any] = {"user_id": user.id if user else None}

    # Hospital master data (always for single-hospital deployment)
    hospital_snapshot = hospital_svc.get_context_snapshot()
    ctx.update(hospital_snapshot)
    ctx["location"] = hospital_snapshot.get("hospital_name")

    # Demo patient for admin playground / unauthenticated testing
    if demo_patient_index is not None:
        demos = hospital_svc.get_demo_patients()
        if 0 <= demo_patient_index < len(demos):
            demo = demos[demo_patient_index]
            ctx["demo_patient"] = demo
            ctx["insurance_provider"] = demo.get("insurance_provider")
            ctx["insurer"] = demo.get("insurance_provider")
            ctx["patient_profile"] = demo

    # Authenticated patient profile from Supabase
    elif user and get_supabase_factory().configured:
        try:
            profile = PatientService().get_profile_by_user(user.id)
            if profile:
                ctx["patient_profile"] = profile.model_dump()
                ctx["insurance_provider"] = profile.insurance_provider
                ctx["insurer"] = profile.insurance_provider or ""
                records = PatientService().get_records(profile.id)
                ctx["medical_records"] = [r.model_dump() for r in records]
        except Exception:
            pass

    if extra:
        ctx.update(extra)
        if extra.get("insurance_provider") and not ctx.get("insurer"):
            ctx["insurer"] = extra["insurance_provider"]

    return ctx

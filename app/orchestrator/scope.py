from __future__ import annotations

import re
from typing import Literal

QueryScope = Literal["healthcare", "out_of_scope"]

OUT_OF_SCOPE_MESSAGE = (
    "I'm a healthcare-only AI assistant. I help with medical triage, symptoms, "
    "medications, lab results, medical records, insurance, prior authorization, "
    "appointments, and related clinical topics.\n\n"
    "Your question is outside my scope — I can't assist with general technology, "
    "coding, deployment, or other non-healthcare requests.\n\n"
    "If you have a health-related question, please ask and I'll route it to the "
    "appropriate clinical agent."
)

# Obvious non-healthcare topics (checked before agent execution)
_NON_HEALTHCARE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bdeploy(ment|ing)?\b.*\b(render|heroku|vercel|aws|azure|gcp|kubernetes|k8s|docker|fly\.io)\b",
        r"\b(render|heroku|vercel)\b.*\bdeploy",
        r"\bhow\s+to\s+(deploy|host|publish|launch)\b.*\b(app|application|website|api|service)\b",
        r"\b(render\.com|github\s+actions|ci/?cd|terraform|ansible)\b",
        r"\bhow\s+to\s+(code|program|build\s+an?\s+app|write\s+(python|javascript|java))\b",
        r"\b(install|setup|configure)\s+(node|npm|pip|docker|postgres|redis)\b",
        r"\b(write|generate|create)\s+(me\s+)?(a\s+)?(poem|essay|story|joke|song|resume)\b",
        r"\b(weather|stock\s+price|sports\s+score|election|politics)\b",
        r"\b(recipe|cook|restaurant)\b(?!.*(allergy|diet|nutrition|diabetes))",
        r"\b(homework|math\s+problem|physics\s+problem)\b(?!.*(medical|clinical|health))",
    ]
]

_HEALTHCARE_SIGNALS: tuple[str, ...] = (
    "symptom",
    "pain",
    "fever",
    "headache",
    "medication",
    "medicine",
    "drug",
    "dose",
    "dosage",
    "patient",
    "doctor",
    "physician",
    "nurse",
    "hospital",
    "clinic",
    "diagnosis",
    "diagnose",
    "treatment",
    "insurance",
    "prior auth",
    "authorization",
    "lab",
    "blood",
    "cbc",
    "mri",
    "xray",
    "x-ray",
    "prescription",
    "allergy",
    "allergies",
    "health",
    "medical",
    "clinical",
    "icd",
    "cpt",
    "ehr",
    "pharmacy",
    "surgery",
    "therapy",
    "cancer",
    "diabetes",
    "hypertension",
    "cholesterol",
    "appointment",
    "specialist",
    "ambulance",
    "emergency room",
    "er visit",
    "hipaa",
    "discharge",
    "vital",
    "heart rate",
    "blood pressure",
    "breathing",
    "cough",
    "nausea",
    "injury",
    "wound",
    "fracture",
    "pregnant",
    "pregnancy",
)


def _has_healthcare_signal(query: str) -> bool:
    q = query.lower()
    return any(signal in q for signal in _HEALTHCARE_SIGNALS)


def _matches_non_healthcare_pattern(query: str) -> bool:
    return any(p.search(query) for p in _NON_HEALTHCARE_PATTERNS)


def detect_query_scope(query: str) -> QueryScope:
    """Return out_of_scope for clearly non-healthcare queries."""
    text = query.strip()
    if not text:
        return "out_of_scope"

    if _has_healthcare_signal(text):
        return "healthcare"

    if _matches_non_healthcare_pattern(text):
        return "out_of_scope"

    # Short tech-ish queries without health context
    tech_hints = (
        "deploy",
        "render",
        "docker",
        "kubernetes",
        "github",
        "api key",
        "fastapi",
        "python script",
        "javascript",
        "database migration",
        "npm install",
        "pip install",
    )
    q_lower = text.lower()
    if any(hint in q_lower for hint in tech_hints):
        return "out_of_scope"

    return "healthcare"

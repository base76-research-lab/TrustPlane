from __future__ import annotations

import os
from enum import Enum
from fastapi import HTTPException


class Tier(str, Enum):
    FREE = "free"
    ENTERPRISE = "enterprise"


_TIER = Tier(os.getenv("COGNOS_TIER", "enterprise").lower())


def get_tier() -> Tier:
    return _TIER


# ---------------------------------------------------------------------------
# Free tier limits
# ---------------------------------------------------------------------------

FREE_LIMITS = {
    "max_tenants": 1,
    "rate_limit": "100/day",
    "webhook_max_endpoints": 1,
    "webhook_max_events_per_day": 100,
    "audit_pdf": False,
    "compliance_report_json": True,
    "compliance_report_pdf": False,
    "multi_tenant": False,
    "fallback_provider": False,
    "session_memory": False,
    "token_compressor": False,
    "rbac_roles": {"admin", "operator"},   # auditor/viewer locked
    "custom_rate_limit": False,
}


def enforce(feature: str) -> None:
    """Raise 402 if feature is locked in current tier."""
    if _TIER == Tier.ENTERPRISE:
        return
    locked = not FREE_LIMITS.get(feature, True)
    if locked:
        raise HTTPException(
            status_code=402,
            detail=f"Feature '{feature}' requires TrustPlane. "
                   f"Upgrade at https://cognos.ai/upgrade",
        )


def enforce_tenant_count(current_count: int) -> None:
    if _TIER == Tier.FREE and current_count >= FREE_LIMITS["max_tenants"]:
        raise HTTPException(
            status_code=402,
            detail="Free tier is limited to 1 tenant. Upgrade to TrustPlane.",
        )


def get_effective_rate_limit(configured: str) -> str:
    """In free tier, cap rate limit regardless of config."""
    if _TIER == Tier.FREE:
        return FREE_LIMITS["rate_limit"]
    return configured


def tier_info() -> dict:
    return {
        "tier": _TIER.value,
        "limits": FREE_LIMITS if _TIER == Tier.FREE else "unlimited",
        "upgrade_url": "https://cognos.ai/upgrade" if _TIER == Tier.FREE else None,
    }

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ROLES = {"admin", "operator", "auditor", "viewer"}

# In production these would come from PostgreSQL / an auth service.
# For now, read from env or use a simple in-process store.
_API_KEY_STORE: dict[str, dict] = {}


def register_api_key(api_key: str, tenant_id: str, role: str = "operator") -> None:
    """Register an API key (used at signup / testing)."""
    _API_KEY_STORE[api_key] = {"tenant_id": tenant_id, "role": role}


def _seed_from_env() -> None:
    """Seed demo key from environment if set."""
    key = os.getenv("COGNOS_GATEWAY_API_KEY")
    tenant = os.getenv("COGNOS_DEFAULT_TENANT", "default")
    if key:
        _API_KEY_STORE[key] = {"tenant_id": tenant, "role": "admin"}


_seed_from_env()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

class AuthContext:
    def __init__(self, tenant_id: str, role: str, api_key: str) -> None:
        self.tenant_id = tenant_id
        self.role = role
        self.api_key = api_key

    def require_role(self, *allowed: str) -> None:
        if self.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{self.role}' is not allowed. Required: {list(allowed)}",
            )


def get_auth_context(
    x_api_key: Annotated[str | None, Header()] = None,
    x_cognos_tenant: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    record = _API_KEY_STORE.get(x_api_key)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    # Allow header to override tenant (within the key's tenant scope for non-admin)
    tenant_id = x_cognos_tenant or record["tenant_id"]
    if record["role"] != "admin" and tenant_id != record["tenant_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch",
        )
    return AuthContext(tenant_id=tenant_id, role=record["role"], api_key=x_api_key)


AuthDep = Annotated[AuthContext, Depends(get_auth_context)]


# ---------------------------------------------------------------------------
# Key generation helper
# ---------------------------------------------------------------------------

def generate_api_key(prefix: str = "ce") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"

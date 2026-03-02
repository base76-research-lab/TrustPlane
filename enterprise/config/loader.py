from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


_ENV_REF = re.compile(r"\$\{([^}]+)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            return os.getenv(m.group(1), m.group(0))
        return _ENV_REF.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_provider_config(tenant_id: str, config_dir: str | None = None) -> dict[str, Any]:
    """Load provider.yaml for a tenant, expanding ${ENV_VAR} references."""
    base = Path(config_dir or os.getenv("COGNOS_CONFIG_DIR", "enterprise/config"))
    tenant_file = base / tenant_id / "provider.yaml"
    default_file = base / "provider.yaml"

    path = tenant_file if tenant_file.exists() else default_file
    if not path.exists():
        return _defaults()

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    return _expand_env(raw)


def _defaults() -> dict[str, Any]:
    return {
        "provider": os.getenv("COGNOS_PROVIDER", "ollama"),
        "model": os.getenv("COGNOS_MODEL", "llama3.2:1b"),
        "api_key": None,
        "target_risk": float(os.getenv("COGNOS_TARGET_RISK", "0.5")),
        "rate_limit": "1000/day",
        "webhook_url": None,
        "session_memory_enabled": True,
        "audit_enabled": True,
        "audit_retention_days": 90,
    }

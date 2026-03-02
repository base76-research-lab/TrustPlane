"""Smoke tests for CognOS Enterprise Gateway (no external deps required)."""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

# Point to gateway/ for proof-engine imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))

os.environ.setdefault("COGNOS_USE_POSTGRES", "false")
os.environ.setdefault("COGNOS_GATEWAY_API_KEY", "test-key")
os.environ.setdefault("COGNOS_DEFAULT_TENANT", "demo")
os.environ.setdefault("COGNOS_PROVIDER", "ollama")

from enterprise.app import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": "test-key", "X-Cognos-Tenant": "demo"}


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_signup():
    resp = client.post("/v1/signup", json={"tenant_id": "acme", "role": "operator"})
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["tenant_id"] == "acme"


def test_chat_no_auth():
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401


def test_provider_health():
    resp = client.get("/v1/providers/health", headers=HEADERS)
    # Provider may not be available in CI, just check auth works
    assert resp.status_code in {200, 502}


def test_audit_export_csv():
    resp = client.get("/v1/audit/export?format=csv", headers=HEADERS)
    assert resp.status_code == 200


def test_policy_pass():
    from gateway.policy import resolve_decision
    decision, risk = resolve_decision("gate", 0.5)
    assert decision == "PASS"
    assert 0.0 <= risk <= 1.0


def test_policy_block():
    from gateway.policy import resolve_decision
    decision, risk = resolve_decision("gate", 0.0)
    assert decision in {"BLOCK", "ESCALATE", "REFINE"}

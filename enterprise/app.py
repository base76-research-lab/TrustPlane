from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Gateway (proof-engine core)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateway"))
from policy import resolve_decision  # noqa: E402

# Enterprise modules
from enterprise.auth.middleware import AuthDep, generate_api_key, register_api_key
from enterprise.auth.rate_limit import check_rate_limit
from enterprise.config.loader import load_provider_config
from enterprise.providers.registry import get_provider
from enterprise.tenants.router import ensure_tenant_schema, save_trace, get_traces
from enterprise.webhooks.dispatcher import dispatch, build_payload
from enterprise.audit.exporter import export_csv, export_pdf

app = FastAPI(
    title="CognOS Enterprise Gateway",
    version="1.0.0",
    description="Pluggable LLM trust-scoring gateway with multi-tenant isolation",
)

_USE_POSTGRES = os.getenv("COGNOS_USE_POSTGRES", "true").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    # Seed demo tenant
    demo_key = os.getenv("COGNOS_GATEWAY_API_KEY", "test-key")
    demo_tenant = os.getenv("COGNOS_DEFAULT_TENANT", "demo")
    register_api_key(demo_key, demo_tenant, role="admin")
    if _USE_POSTGRES:
        try:
            await ensure_tenant_schema(demo_tenant)
        except Exception as exc:
            print(f"[WARN] PostgreSQL not available, falling back to SQLite: {exc}")
    else:
        # SQLite fallback for development
        import sys
        sys.path.insert(0, "gateway")
        from trace_store import init_db
        init_db()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "cognos-enterprise-gateway", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Signup (SaaS)
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    tenant_id: str
    email: str | None = None
    role: str = "operator"


@app.post("/v1/signup")
async def signup(req: SignupRequest) -> dict[str, str]:
    api_key = generate_api_key()
    register_api_key(api_key, req.tenant_id, role=req.role)
    if _USE_POSTGRES:
        try:
            await ensure_tenant_schema(req.tenant_id)
        except Exception:
            pass
    return {"tenant_id": req.tenant_id, "api_key": api_key, "role": req.role}


# ---------------------------------------------------------------------------
# Provider health check
# ---------------------------------------------------------------------------

@app.get("/v1/providers/health")
async def provider_health(auth: AuthDep) -> dict[str, Any]:
    cfg = load_provider_config(auth.tenant_id)
    provider = get_provider(cfg["provider"], api_key=cfg.get("api_key"))
    ok = await provider.health()
    return {"provider": cfg["provider"], "healthy": ok}


# ---------------------------------------------------------------------------
# Chat completions
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, auth: AuthDep) -> Response:
    # Rate limiting
    cfg = load_provider_config(auth.tenant_id)
    rate_str = cfg.get("rate_limit", "1000/day")
    allowed, remaining = await check_rate_limit(auth.tenant_id, rate_str)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    trace_id = f"tr_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = payload.get("messages", [])
    model = payload.get("model", cfg.get("model", "llama3.2:1b"))
    stream = payload.get("stream", False)

    # Trust scoring
    mode = payload.get("cognos", {}).get("mode", "gate")
    target_risk = cfg.get("target_risk", 0.5)
    decision, risk = resolve_decision(mode, target_risk)
    trust_score = 1.0 - risk
    policy = payload.get("cognos", {}).get("policy_id", "enterprise_v1")

    # Block immediately
    if decision == "BLOCK":
        _save_trace_bg(
            auth.tenant_id, trace_id, created_at, decision, policy,
            trust_score, risk, stream, 403, model, payload,
        )
        raise HTTPException(status_code=403, detail=f"Request blocked. Trust score: {trust_score:.2f}")

    # Route to LLM provider
    provider_name = cfg.get("provider", "ollama")
    provider = get_provider(provider_name, api_key=cfg.get("api_key"))

    try:
        result = await provider.chat(messages, model, stream=stream)
    except Exception as exc:
        # Try fallback provider
        fallback = cfg.get("fallback")
        if fallback:
            try:
                fallback_provider = get_provider(fallback)
                result = await fallback_provider.chat(messages, model, stream=stream)
            except Exception:
                raise HTTPException(status_code=502, detail=f"Provider error: {exc}")
        else:
            raise HTTPException(status_code=502, detail=f"Provider error: {exc}")

    # Webhook on ESCALATE
    webhook_url = cfg.get("webhook_url")
    if webhook_url and decision in {"ESCALATE", "BLOCK"}:
        wh_payload = build_payload(trace_id, decision, trust_score, auth.tenant_id, model)
        await dispatch(webhook_url, wh_payload)

    # Persist trace
    _save_trace_bg(
        auth.tenant_id, trace_id, created_at, decision, policy,
        trust_score, risk, stream, 200, model, payload,
    )

    # Add epistemic headers
    headers = {
        "X-Cognos-Trace-Id": trace_id,
        "X-Cognos-Decision": decision,
        "X-Cognos-Trust-Score": f"{trust_score:.4f}",
        "X-Cognos-Policy": policy,
        "X-RateLimit-Remaining": str(remaining),
    }
    return JSONResponse(content=result, headers=headers)


# ---------------------------------------------------------------------------
# Audit export
# ---------------------------------------------------------------------------

@app.get("/v1/audit/export")
async def audit_export(
    auth: AuthDep,
    format: str = "csv",
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> Response:
    auth.require_role("admin", "auditor")

    if _USE_POSTGRES:
        traces = await get_traces(auth.tenant_id, from_ts=from_ts, to_ts=to_ts)
    else:
        traces = _get_sqlite_traces(from_ts, to_ts)

    if format == "pdf":
        pdf_bytes = export_pdf(traces, auth.tenant_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=cognos_audit_{auth.tenant_id}.pdf"},
        )

    csv_data = export_csv(traces)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cognos_audit_{auth.tenant_id}.csv"},
    )


# ---------------------------------------------------------------------------
# Webhook test endpoint
# ---------------------------------------------------------------------------

class WebhookTestRequest(BaseModel):
    decision: str = "ESCALATE"
    trust_score: float = 0.3


@app.post("/v1/test/webhook")
async def test_webhook(req: WebhookTestRequest, auth: AuthDep) -> dict[str, str]:
    cfg = load_provider_config(auth.tenant_id)
    webhook_url = cfg.get("webhook_url")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="No webhook_url configured for this tenant")
    payload = build_payload(
        trace_id=f"tr_test_{uuid.uuid4().hex[:8]}",
        decision=req.decision,
        trust_score=req.trust_score,
        tenant_id=auth.tenant_id,
    )
    await dispatch(webhook_url, payload)
    return {"status": "dispatched", "webhook_url": webhook_url}


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

@app.get("/v1/traces/{trace_id}")
async def get_trace_endpoint(trace_id: str, auth: AuthDep) -> dict[str, Any]:
    if _USE_POSTGRES:
        rows = await get_traces(auth.tenant_id)
        match = next((r for r in rows if r.get("trace_id") == trace_id), None)
    else:
        import sys
        sys.path.insert(0, "gateway")
        from trace_store import get_trace
        match = get_trace(trace_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return match


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

import asyncio


def _save_trace_bg(
    tenant_id: str, trace_id: str, created_at: str, decision: str,
    policy: str, trust_score: float, risk: float, stream: bool,
    status_code: int, model: str, payload: dict,
) -> None:
    record = {
        "trace_id": trace_id,
        "created_at": created_at,
        "decision": decision,
        "policy": policy,
        "trust_score": trust_score,
        "risk": risk,
        "is_stream": stream,
        "status_code": status_code,
        "model": model,
        "envelope": payload,
        "metadata": {},
    }
    if _USE_POSTGRES:
        asyncio.create_task(save_trace(tenant_id, record))
    else:
        import sys
        sys.path.insert(0, "gateway")
        from trace_store import save_trace as sqlite_save
        sqlite_save(record)


def _get_sqlite_traces(from_ts: str | None, to_ts: str | None) -> list[dict]:
    import sys, sqlite3, json
    sys.path.insert(0, "gateway")
    from trace_store import _resolve_db_path
    db_path = _resolve_db_path()
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM traces ORDER BY created_at DESC LIMIT 1000").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

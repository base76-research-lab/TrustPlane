from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
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
from enterprise.tenants.router import (
    ensure_tenant_schema, save_trace, get_traces,
    save_report, get_reports, get_report, get_report_pdf,
    override_trace, purge_expired_traces,
)
from enterprise.webhooks.dispatcher import dispatch, build_payload
from enterprise.audit.exporter import export_csv, export_pdf
from enterprise.audit.compliance_report import build_compliance_report, render_pdf as render_compliance_pdf
from enterprise.tier import enforce, enforce_tenant_count, get_effective_rate_limit, tier_info

app = FastAPI(
    title="TrustPlane Gateway",
    version="1.0.0",
    description="Pluggable LLM trust-scoring gateway with multi-tenant isolation",
)

_CORS_ORIGINS = os.getenv(
    "TRUSTPLANE_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            # Schedule daily retention purge in background
            asyncio.create_task(_retention_purge_loop(demo_tenant))
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
async def healthz() -> dict:
    return {"status": "ok", "service": "trustplane-gateway", "version": "1.0.0", **tier_info()}


# ---------------------------------------------------------------------------
# Signup (SaaS)
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    tenant_id: str
    email: str | None = None
    role: str = "operator"


@app.post("/v1/signup")
async def signup(req: SignupRequest) -> dict[str, str]:
    enforce_tenant_count(len(set(v["tenant_id"] for v in __import__("enterprise.auth.middleware", fromlist=["_API_KEY_STORE"])._API_KEY_STORE.values())))
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

@app.get("/v1/tier")
async def get_tier_info(auth: AuthDep) -> dict:
    return tier_info()


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
    # Rate limiting (free tier capped at 100/day)
    cfg = load_provider_config(auth.tenant_id)
    rate_str = get_effective_rate_limit(cfg.get("rate_limit", "1000/day"))
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

    # Webhook on ESCALATE (free tier: limited events, enforce at dispatch)
    webhook_url = cfg.get("webhook_url")
    if webhook_url and decision in {"ESCALATE", "BLOCK"}:
        enforce("webhook_max_events_per_day")  # no-op in enterprise
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
        enforce("audit_pdf")
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
# Compliance reports
# ---------------------------------------------------------------------------

class ComplianceReportRequest(BaseModel):
    from_ts: str = "2026-01-01"
    to_ts: str = "2099-12-31"
    format: str = "json"  # "json" | "pdf"

    class Config:
        # Allow "from" as alias since it's a Python keyword
        populate_by_name = True

    @classmethod
    def from_alias(cls, data: dict) -> "ComplianceReportRequest":
        mapped = dict(data)
        if "from" in mapped:
            mapped["from_ts"] = mapped.pop("from")
        if "to" in mapped:
            mapped["to_ts"] = mapped.pop("to")
        return cls(**mapped)


@app.post("/v1/audit/compliance-report")
async def compliance_report_endpoint(
    request: Request,
    auth: AuthDep,
) -> Response:
    auth.require_role("admin", "auditor")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from_ts = body.get("from", body.get("from_ts", "2026-01-01"))
    to_ts = body.get("to", body.get("to_ts", "2099-12-31"))
    fmt = body.get("format", "json").lower()

    if fmt == "pdf":
        enforce("compliance_report_pdf")
    else:
        enforce("compliance_report_json")

    if _USE_POSTGRES:
        traces = await get_traces(auth.tenant_id, from_ts=from_ts, to_ts=to_ts)
    else:
        traces = _get_sqlite_traces(from_ts, to_ts)

    report = build_compliance_report(traces, auth.tenant_id, from_ts, to_ts)

    # Persist report (best-effort)
    if _USE_POSTGRES:
        try:
            await ensure_tenant_schema(auth.tenant_id)
            summary = report.to_dict()
            # Store top-50 traces sample in raw_stats for PDF appendix
            summary["raw_stats"]["_traces_sample"] = traces[:50]
            pdf_bytes = render_compliance_pdf(report, auth.tenant_id) if fmt == "pdf" else None
            await save_report(
                auth.tenant_id,
                report.report_id,
                from_ts,
                to_ts,
                report.overall_risk_level,
                summary,
                pdf_bytes,
            )
        except Exception as exc:
            print(f"[WARN] Could not persist compliance report: {exc}")

    if fmt == "pdf":
        # Inject traces sample for PDF appendix
        report.raw_stats["_traces_sample"] = traces[:50]
        pdf_bytes = render_compliance_pdf(report, auth.tenant_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=compliance_{auth.tenant_id}_{report.report_id}.pdf"
                )
            },
        )

    report_dict = report.to_dict()
    report_dict.pop("raw_stats", None)  # keep JSON response clean; raw_stats in separate field
    report_dict["raw_stats"] = {
        k: v for k, v in report.raw_stats.items() if k != "_traces_sample"
    }
    return JSONResponse(content=report_dict)


@app.get("/v1/reports/")
async def list_reports(auth: AuthDep) -> list[dict]:
    auth.require_role("admin", "auditor")
    if not _USE_POSTGRES:
        return []
    rows = await get_reports(auth.tenant_id)
    # Serialise datetime objects
    result = []
    for r in rows:
        row = dict(r)
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        result.append(row)
    return result


@app.get("/v1/reports/{report_id}")
async def get_report_endpoint(report_id: str, auth: AuthDep) -> dict[str, Any]:
    auth.require_role("admin", "auditor")
    if not _USE_POSTGRES:
        raise HTTPException(status_code=404, detail="Report not found (SQLite mode)")
    row = await get_report(auth.tenant_id, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    result = dict(row)
    for k, v in result.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
    return result


@app.get("/v1/reports/{report_id}/pdf")
async def get_report_pdf_endpoint(report_id: str, auth: AuthDep) -> Response:
    auth.require_role("admin", "auditor")
    enforce("compliance_report_pdf")
    if not _USE_POSTGRES:
        raise HTTPException(status_code=404, detail="Report not found (SQLite mode)")
    pdf = await get_report_pdf(auth.tenant_id, report_id)
    if pdf is None:
        raise HTTPException(status_code=404, detail="PDF not found for this report")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report_id}.pdf"},
    )


# ---------------------------------------------------------------------------
# Human oversight — trace override (Art. 14)
# ---------------------------------------------------------------------------

class OverrideRequest(BaseModel):
    reason: str


@app.post("/v1/traces/{trace_id}/override")
async def override_trace_endpoint(
    trace_id: str,
    req: OverrideRequest,
    auth: AuthDep,
) -> dict[str, Any]:
    """
    Mark a BLOCK or ESCALATE trace as human-reviewed and approved.
    Records who overrode it, when, and the stated reason.
    Required for EU AI Act Art. 14 human oversight compliance.
    """
    auth.require_role("admin", "auditor")
    if not req.reason or len(req.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="reason must be at least 5 characters")

    if _USE_POSTGRES:
        updated = await override_trace(
            auth.tenant_id,
            trace_id,
            override_by=auth.role + ":" + auth.api_key[-6:],
            reason=req.reason.strip(),
        )
        if not updated:
            raise HTTPException(
                status_code=404,
                detail="Trace not found, not BLOCK/ESCALATE, or already overridden",
            )
    else:
        # SQLite mode — no override support, log a warning
        print(f"[WARN] Override requested for {trace_id} but SQLite mode has no override support")
        updated = False

    return {
        "trace_id": trace_id,
        "overridden": updated,
        "override_by": auth.role,
        "message": "Trace marked as human-reviewed" if updated else "SQLite mode — override not persisted",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

import asyncio


async def _retention_purge_loop(tenant_id: str) -> None:
    """Daily background task: purge expired traces for the given tenant."""
    _PURGE_INTERVAL = int(os.getenv("COGNOS_PURGE_INTERVAL_HOURS", "24")) * 3600
    while True:
        await asyncio.sleep(_PURGE_INTERVAL)
        try:
            deleted = await purge_expired_traces(tenant_id)
            if deleted:
                print(f"[INFO] Retention purge: removed {deleted} expired traces for tenant '{tenant_id}'")
        except Exception as exc:
            print(f"[WARN] Retention purge failed for tenant '{tenant_id}': {exc}")


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
        cfg = load_provider_config(tenant_id)
        retention_days = max(180, int(cfg.get("audit_retention_days", 180)))
        asyncio.create_task(save_trace(tenant_id, record, retention_days=retention_days))
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

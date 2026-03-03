from __future__ import annotations

import os
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# PostgreSQL multi-tenant trace store
# Each tenant gets its own schema: tenant_{id}
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cognos:cognos@localhost:5432/cognos")


async def get_connection() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


async def ensure_tenant_schema(tenant_id: str) -> None:
    """Create schema and traces table for a tenant if they don't exist."""
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{schema}".reports (
                report_id   TEXT PRIMARY KEY,
                created_at  TIMESTAMPTZ DEFAULT now(),
                period_from TIMESTAMPTZ,
                period_to   TIMESTAMPTZ,
                risk_level  TEXT,
                summary_json JSONB,
                pdf_blob    BYTEA
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{schema}".traces (
                trace_id        TEXT PRIMARY KEY,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                decision        TEXT NOT NULL,
                policy          TEXT NOT NULL,
                trust_score     DOUBLE PRECISION NOT NULL,
                risk            DOUBLE PRECISION NOT NULL,
                is_stream       BOOLEAN NOT NULL DEFAULT false,
                status_code     INTEGER NOT NULL DEFAULT 200,
                model           TEXT,
                request_fp      JSONB,
                response_fp     JSONB,
                envelope        JSONB,
                metadata        JSONB,
                expires_at      TIMESTAMPTZ,
                overridden      BOOLEAN NOT NULL DEFAULT false,
                override_by     TEXT,
                override_at     TIMESTAMPTZ,
                override_reason TEXT
            )
        """)
        # Add new columns to existing tables (idempotent migrations)
        for col, definition in [
            ("expires_at",      "TIMESTAMPTZ"),
            ("overridden",      "BOOLEAN NOT NULL DEFAULT false"),
            ("override_by",     "TEXT"),
            ("override_at",     "TIMESTAMPTZ"),
            ("override_reason", "TEXT"),
        ]:
            try:
                await conn.execute(
                    f'ALTER TABLE "{schema}".traces ADD COLUMN IF NOT EXISTS {col} {definition}'
                )
            except Exception:
                pass  # column already exists or DB doesn't support IF NOT EXISTS
    finally:
        await conn.close()


async def save_trace(
    tenant_id: str,
    record: dict[str, Any],
    retention_days: int = 180,
) -> None:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        await conn.execute(
            f"""
            INSERT INTO "{schema}".traces
              (trace_id, created_at, decision, policy, trust_score, risk,
               is_stream, status_code, model, request_fp, response_fp, envelope, metadata,
               expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12::jsonb, $13::jsonb,
                    $2::timestamptz + ($14 || ' days')::interval)
            ON CONFLICT (trace_id) DO NOTHING
            """,
            record["trace_id"],
            record["created_at"],
            record["decision"],
            record["policy"],
            float(record.get("trust_score", 0.0)),
            float(record.get("risk", 0.0)),
            bool(record.get("is_stream", False)),
            int(record.get("status_code", 200)),
            record.get("model"),
            _json(record.get("request_fingerprint")),
            _json(record.get("response_fingerprint")),
            _json(record.get("envelope")),
            _json(record.get("metadata")),
            str(retention_days),
        )
    finally:
        await conn.close()


async def override_trace(
    tenant_id: str,
    trace_id: str,
    override_by: str,
    reason: str,
) -> bool:
    """
    Mark a BLOCK or ESCALATE trace as human-reviewed and approved (overridden).
    Returns True if the trace was found and updated, False otherwise.
    """
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        result = await conn.execute(
            f"""
            UPDATE "{schema}".traces
            SET overridden = true,
                override_by = $2,
                override_at = now(),
                override_reason = $3
            WHERE trace_id = $1
              AND decision IN ('BLOCK', 'ESCALATE')
              AND overridden = false
            """,
            trace_id,
            override_by,
            reason,
        )
        return result == "UPDATE 1"
    finally:
        await conn.close()


async def purge_expired_traces(tenant_id: str) -> int:
    """
    Delete traces whose expires_at is in the past.
    Returns the number of deleted rows.
    Art. 12: deployers must retain logs for at least 6 months (180 days).
    Purge only removes traces beyond the configured retention window.
    """
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        result = await conn.execute(
            f"""
            DELETE FROM "{schema}".traces
            WHERE expires_at IS NOT NULL
              AND expires_at < now()
            """,
        )
        # asyncpg returns e.g. "DELETE 42"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0
    finally:
        await conn.close()


async def get_traces(
    tenant_id: str,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        query = f'SELECT * FROM "{schema}".traces WHERE true'
        args: list[Any] = []
        if from_ts:
            args.append(from_ts)
            query += f" AND created_at >= ${len(args)}"
        if to_ts:
            args.append(to_ts)
            query += f" AND created_at <= ${len(args)}"
        query += f" ORDER BY created_at DESC LIMIT {limit}"
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def save_report(
    tenant_id: str,
    report_id: str,
    period_from: str,
    period_to: str,
    risk_level: str,
    summary_json: dict,
    pdf_blob: bytes | None = None,
) -> None:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        await conn.execute(
            f"""
            INSERT INTO "{schema}".reports
              (report_id, period_from, period_to, risk_level, summary_json, pdf_blob)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            ON CONFLICT (report_id) DO NOTHING
            """,
            report_id,
            period_from,
            period_to,
            risk_level,
            _json(summary_json),
            pdf_blob,
        )
    finally:
        await conn.close()


async def get_reports(tenant_id: str) -> list[dict[str, Any]]:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            f"""
            SELECT report_id, created_at, period_from, period_to, risk_level
            FROM "{schema}".reports
            ORDER BY created_at DESC
            LIMIT 200
            """
        )
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        await conn.close()


async def get_report(tenant_id: str, report_id: str) -> dict[str, Any] | None:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            f"""
            SELECT report_id, created_at, period_from, period_to, risk_level, summary_json
            FROM "{schema}".reports
            WHERE report_id = $1
            """,
            report_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_report_pdf(tenant_id: str, report_id: str) -> bytes | None:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            f'SELECT pdf_blob FROM "{schema}".reports WHERE report_id = $1',
            report_id,
        )
        if row is None:
            return None
        return bytes(row["pdf_blob"]) if row["pdf_blob"] else None
    finally:
        await conn.close()


def _schema(tenant_id: str) -> str:
    safe = tenant_id.replace("-", "_").replace(".", "_")[:63]
    return f"tenant_{safe}"


def _json(value: Any) -> str | None:
    if value is None:
        return None
    import json
    return json.dumps(value)

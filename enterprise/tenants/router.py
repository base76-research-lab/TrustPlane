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
                metadata        JSONB
            )
        """)
    finally:
        await conn.close()


async def save_trace(tenant_id: str, record: dict[str, Any]) -> None:
    schema = _schema(tenant_id)
    conn = await get_connection()
    try:
        await conn.execute(
            f"""
            INSERT INTO "{schema}".traces
              (trace_id, created_at, decision, policy, trust_score, risk,
               is_stream, status_code, model, request_fp, response_fp, envelope, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12::jsonb, $13::jsonb)
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
        )
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


def _schema(tenant_id: str) -> str:
    safe = tenant_id.replace("-", "_").replace(".", "_")[:63]
    return f"tenant_{safe}"


def _json(value: Any) -> str | None:
    if value is None:
        return None
    import json
    return json.dumps(value)

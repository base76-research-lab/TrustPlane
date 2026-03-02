from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


async def dispatch(webhook_url: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget webhook dispatch with exponential backoff retries."""
    asyncio.create_task(_send_with_retry(webhook_url, payload))


async def _send_with_retry(url: str, payload: dict[str, Any]) -> None:
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code < 500:
                    logger.info("Webhook delivered to %s (status=%s)", url, resp.status_code)
                    return
                logger.warning("Webhook %s returned %s, retrying…", url, resp.status_code)
        except Exception as exc:
            logger.warning("Webhook attempt %d failed: %s", attempt + 1, exc)

        if attempt < _MAX_RETRIES - 1:
            wait = _BACKOFF_BASE ** attempt
            await asyncio.sleep(wait)

    logger.error("Webhook %s failed after %d attempts", url, _MAX_RETRIES)


def build_payload(
    trace_id: str,
    decision: str,
    trust_score: float,
    tenant_id: str,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import datetime
    payload = {
        "trace_id": trace_id,
        "decision": decision,
        "trust_score": trust_score,
        "tenant_id": tenant_id,
        "model": model,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload

# CognOS Enterprise — Claude Code & Anthropic API Setup

Connect CognOS Enterprise to Claude Code as an MCP server, or use the Anthropic provider adapter directly in your application.

---

## Option A: Claude Code via MCP

CognOS Enterprise exposes itself as an MCP server. Claude Code can then call trust-scoring tools directly during its own reasoning process — verifying outputs before acting on them.

### 1. Install MCP dependencies

```bash
cd Cognos-enterprise/mcp
pip install -r requirements.txt
```

### 2. Start the enterprise gateway

```bash
docker-compose up
# or
COGNOS_USE_POSTGRES=false uvicorn enterprise.app:app --port 8788
```

### 3. Register in Claude Code settings

Edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "cognos": {
      "command": "python",
      "args": ["/absolute/path/to/Cognos-enterprise/mcp/server.py"],
      "env": {
        "COGNOS_BASE_URL": "http://127.0.0.1:8788",
        "COGNOS_API_KEY": "your-api-key",
        "COGNOS_TENANT": "your-tenant-id"
      }
    }
  }
}
```

### 4. Restart Claude Code

Claude Code now has access to these tools:

| Tool | What it does |
|---|---|
| `verify_output` | Score any content for epistemic risk before using it |
| `get_trace` | Retrieve full audit trail for a trace ID |
| `create_trust_report` | Generate EU AI Act compliance report |
| `healthz` | Check gateway availability |

### Usage example in Claude Code

```
Use CognOS to verify this diagnosis before including it in the report:
"Patient presents with elevated troponin. Recommend immediate intervention."
```

Claude Code calls `verify_output` → gets trust score → decides whether to proceed, refine, or escalate.

---

## Option B: Anthropic API as LLM backend

Use Claude (claude-sonnet-4-6, claude-opus-4-6, etc.) as the LLM behind CognOS Enterprise trust scoring.

### Configure provider.yaml

```yaml
provider: anthropic
model: claude-sonnet-4-6
api_key: ${ANTHROPIC_API_KEY}
target_risk: 0.3
fallback: ollama
```

### Or via environment

```bash
COGNOS_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
COGNOS_MODEL=claude-sonnet-4-6
```

### Request format

Identical to OpenAI — CognOS normalizes all providers:

```bash
curl -X POST http://localhost:8788/v1/chat/completions \
  -H "X-API-Key: your-key" \
  -H "X-Cognos-Tenant: your-tenant" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Summarize this contract."}],
    "cognos": {"mode": "gate", "target_risk": 0.2}
  }'
```

Response includes epistemic headers regardless of which provider answered:

```
X-Cognos-Trust-Score: 0.9142
X-Cognos-Decision: PASS
X-Cognos-Trace-Id: tr_f92a441c
```

---

## Option C: CognOS as trust layer for Claude API calls

Wrap your existing Anthropic SDK calls through the CognOS gateway:

```python
import httpx

COGNOS_URL = "http://localhost:8788/v1/chat/completions"
HEADERS = {
    "X-API-Key": "your-cognos-key",
    "X-Cognos-Tenant": "your-tenant",
    "Content-Type": "application/json",
}

async def trusted_claude(messages: list, target_risk: float = 0.2):
    payload = {
        "model": "anthropic/claude-sonnet-4-6",
        "messages": messages,
        "cognos": {"mode": "gate", "target_risk": target_risk},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(COGNOS_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()

    decision = resp.headers.get("X-Cognos-Decision")
    trust_score = float(resp.headers.get("X-Cognos-Trust-Score", 0))
    trace_id = resp.headers.get("X-Cognos-Trace-Id")

    if decision == "BLOCK":
        raise ValueError(f"Request blocked by CognOS (trust={trust_score:.2f})")
    if decision == "ESCALATE":
        # Trigger your human review workflow here
        notify_reviewer(trace_id, trust_score)

    return resp.json(), trace_id
```

Every Claude API call now has a trust score, a trace ID, and a decision in the audit log.

---

## Supported Anthropic models

Any model available via Anthropic API works as a drop-in:

```yaml
model: claude-opus-4-6        # Highest capability
model: claude-sonnet-4-6      # Balanced (recommended)
model: claude-haiku-4-5-20251001  # Fastest, lowest cost
```

---

## Troubleshooting

**MCP not connecting**
- Use absolute path in settings.json
- Verify gateway is running: `curl http://localhost:8788/healthz`
- Restart Claude Code fully after editing settings.json

**Anthropic API errors**
- Check `ANTHROPIC_API_KEY` is set in `.env`
- Verify model name matches Anthropic's current model IDs
- CognOS will try `fallback` provider automatically if configured

**Trust score always 0.88**
- Default `base_risk` in policy.py is 0.12, giving trust = 0.88
- This is correct for the basic configuration
- Plug in domain-specific uncertainty signals to get dynamic scoring

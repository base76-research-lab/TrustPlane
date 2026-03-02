# CognOS Enterprise

**The AI Trust Control Plane for production LLM systems.**

CognOS Enterprise intercepts every LLM request, scores it for epistemic uncertainty, and enforces your risk policy before the response reaches your users. Every decision is logged, auditable, and EU AI Act compliant.

Built for organizations where AI failures have consequences.

---

## Why this exists

AI failures in production are not edge cases. They are a category of operational risk that most teams have no infrastructure to detect, prevent, or document.

A model hallucinating a medical dosage. A legal assistant citing a case that doesn't exist. A financial assistant giving advice it has no basis for. These are not hypothetical — they happen every day, silently, in systems that have no visibility layer between the LLM and the user.

The cost of an AI failure is not the API call. It is liability, compliance exposure, reputational damage, and in regulated industries, regulatory action.

CognOS Enterprise is the control plane that sits between your application and any LLM, measuring uncertainty before trust is granted.

---

## How it works

Every request is scored using the epistemic trust formula:

```
C = p × (1 − Ue − Ua)
```

- `p` — prior confidence in the model for this request type
- `Ue` — epistemic uncertainty (reducible: what the model doesn't know)
- `Ua` — aleatoric uncertainty (irreducible: noise inherent in the domain)

The result is a trust score between 0 and 1. Your policy determines what happens next.

| Trust score | Decision | Action |
|---|---|---|
| Above threshold | `PASS` | Request forwarded |
| Threshold − 0.2 | `REFINE` | Warning headers, logged |
| Threshold − 0.4 | `ESCALATE` | Webhook triggered, human notified |
| Below minimum | `BLOCK` | Request rejected, trace saved |

Every response carries the decision in its headers:

```
X-Cognos-Trust-Score: 0.8731
X-Cognos-Decision: PASS
X-Cognos-Trace-Id: tr_a3f91c2d44b1
X-Cognos-Policy: enterprise_v1
```

---

## Evidence base

The trust-scoring model is not a heuristic. It is grounded in epistemic theory and validated through empirical work published at [Base76 Research Lab](https://github.com/base76-research-lab).

**OSS core:** [cognos-proof-engine](https://github.com/base76-research-lab/cognos-proof-engine) — the scoring engine is open source, auditable, and independently verifiable. The formula, the decision thresholds, and the policy engine are all inspectable.

**Published research:** The Field-Node-Cockpit (FNC) framework underlying the model has been through peer review. See [Applied AI Philosophy](https://github.com/Applied-Ai-Philosophy) for the full publication record.

**Falsifiability:** The threshold model makes testable predictions. A system calibrated to `target_risk: 0.3` should escalate measurably more than one set to `0.7`. This is testable, loggable, and reportable — which is the point.

If your compliance team, security team, or legal counsel needs to understand how the scoring works, there is source code and published theory to show them.

---

## Capabilities

### Pluggable LLM backend
One control plane. Every provider. Switch without changing application code.

```yaml
provider: ollama          # On-premise, air-gapped
provider: openai          # GPT-4o, o1, o3
provider: anthropic       # Claude 3.5, Claude 4
provider: groq            # High-throughput inference
provider: cerebras        # Low-latency inference
```

Fallback providers configurable for zero-downtime failover.

### Multi-tenant isolation
PostgreSQL schema-per-tenant. No data shared between organizations.

```
tenant_acme.traces
tenant_globocorp.traces
tenant_healthsystem.traces
```

### Human oversight triggers
Webhook dispatch on ESCALATE and BLOCK. Your incident management system receives the signal before your users receive the response.

```json
{
  "trace_id": "tr_a3f91c2d44b1",
  "decision": "ESCALATE",
  "trust_score": 0.31,
  "tenant_id": "acme",
  "timestamp": "2026-03-02T14:22:11Z"
}
```

### Audit trail
Complete trace history for every request. Exportable as CSV or EU AI Act Article 13 PDF report.

```bash
curl -H "X-API-Key: your-key" \
  "https://your-gateway/v1/audit/export?format=pdf&from=2026-01-01" \
  -o compliance_report.pdf
```

### Deployment options
Self-hosted via Docker Compose (your infrastructure, your data) or SaaS (managed, zero-ops).

---

## Claude Code & Anthropic API

CognOS Enterprise integrates with Anthropic in two directions.

**Claude as LLM backend** — use any Claude model (Opus, Sonnet, Haiku) as the provider behind the trust-scoring gateway:

```yaml
# enterprise/config/provider.yaml
provider: anthropic
model: claude-sonnet-4-6
api_key: ${ANTHROPIC_API_KEY}
target_risk: 0.3
fallback: ollama
```

**CognOS as MCP server for Claude Code** — expose trust verification as tools that Claude Code can call during its own reasoning:

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "cognos": {
      "command": "python",
      "args": ["/path/to/Cognos-enterprise/mcp/server.py"],
      "env": {
        "COGNOS_BASE_URL": "http://127.0.0.1:8788",
        "COGNOS_API_KEY": "your-key",
        "COGNOS_TENANT": "your-tenant"
      }
    }
  }
}
```

Claude Code then has access to `verify_output`, `get_trace`, and `create_trust_report` as native tools — scoring its own outputs before acting on them.

Full setup guide: [mcp/CLAUDE_CODE_SETUP.md](mcp/CLAUDE_CODE_SETUP.md)

---

## Quickstart

```bash
git clone https://github.com/base76-research-lab/Cognos-enterprise.git
cd Cognos-enterprise
cp .env.example .env        # Set provider + API key
docker-compose up

curl -X POST http://localhost:8788/v1/chat/completions \
  -H "X-API-Key: test-key" \
  -H "X-Cognos-Tenant: demo" \
  -H "Content-Type: application/json" \
  -d '{"model":"ollama/llama3.2:1b","messages":[{"role":"user","content":"Hello"}]}'
```

---

## Architecture

```
Your Application
       │
       ▼
CognOS Enterprise          — trust scoring, policy enforcement
       │                   — RBAC, rate limiting, audit logging
       │                   — webhook dispatch, tenant isolation
       │
       ├── Ollama           (on-premise)
       ├── OpenAI
       ├── Anthropic
       ├── Groq
       └── Cerebras

PostgreSQL                 — per-tenant audit trail
Redis                      — rate limiting
Dashboard (Next.js)        — visibility layer
```

---

## EU AI Act compliance

CognOS Enterprise is designed for organizations operating AI systems classified as high-risk under EU AI Act Annex III.

| Article | Requirement | How CognOS addresses it |
|---|---|---|
| Art. 9 | Risk management system | Continuous epistemic scoring on every inference |
| Art. 12 | Record-keeping | Immutable trace log with trace IDs and timestamps |
| Art. 13 | Transparency | Automated PDF reports with full attestation summary |
| Art. 14 | Human oversight | Webhook escalation before downstream consequences |

Full compliance guide: [docs/EU_AI_ACT.md](docs/EU_AI_ACT.md)

---

## Pricing

### Free
Open-source core. 1 tenant. 100 requests/day. CSV export.
Sufficient for evaluation and development.
[→ cognos-proof-engine](https://github.com/base76-research-lab/cognos-proof-engine)

### SaaS — from €499/month per tenant
Hosted. Zero infrastructure. Full enterprise feature set.
Suitable for teams that want to deploy quickly without managing infrastructure.

### Self-hosted license — from €25,000/year
Run CognOS on your own infrastructure. Full source access. Air-gap compatible.
Suitable for regulated industries, government, and organizations with data residency requirements.

### Enterprise consulting bundle
Architecture review, policy calibration, compliance documentation, and ongoing support.
Suitable for organizations deploying AI in high-risk domains (healthcare, legal, finance, public sector).

Contact: [bjorn@base76.se](mailto:bjorn@base76.se)

---

## Free vs Enterprise

| Feature | Free | Enterprise |
|---|---|---|
| Trust scoring (PASS/REFINE/ESCALATE/BLOCK) | ✓ | ✓ |
| All LLM providers | ✓ | ✓ |
| Trace history + CSV export | ✓ | ✓ |
| Webhooks | 1 endpoint / 100 events/day | Unlimited |
| Tenants | 1 | Unlimited |
| Rate limit | 100 req/day | Configurable |
| PDF audit reports (EU AI Act) | ✗ | ✓ |
| Fallback providers | ✗ | ✓ |
| Custom RBAC roles | ✗ | ✓ |
| Session memory | ✗ | ✓ |
| Token compression | ✗ | ✓ |
| SLA + support | ✗ | ✓ |

---

## Built on open source

Enterprise is the production layer on top of [cognos-proof-engine](https://github.com/base76-research-lab/cognos-proof-engine) (MIT). The scoring engine is open and auditable. The enterprise layer adds multi-tenancy, auth, webhooks, audit exports, and commercial support.

Related:
- [cognos-session-memory](https://github.com/base76-research-lab/cognos-session-memory) — Verified context injection
- [token-compressor](https://github.com/base76-research-lab/token-compressor) — Context compression for long sessions

---

*[Base76 Research Lab](https://base76.se) — Sjöbo, Sweden*

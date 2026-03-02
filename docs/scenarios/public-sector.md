# Scenario: Public Sector AI — Sovereign Deployment

## Context

A government agency deploys AI for citizen-facing document processing and internal policy analysis. All data must remain within national infrastructure. No external API calls permitted.

**Regulatory context:** EU AI Act (public authority = high-risk by definition), national data sovereignty requirements, potential NIS2 compliance.

**Constraint:** Zero tolerance for data leaving the air-gapped network.

---

## Deployment

```
┌──────────────────────────────────────────────────────────────┐
│              Government Data Center (air-gapped)              │
│                                                              │
│  ┌──────────────┐          ┌──────────────────────────────┐  │
│  │  Citizen     │  HTTPS   │         TrustPlane            │  │
│  │  Services    │─────────▶│                              │  │
│  │  Portal      │          │  COGNOS_TIER=enterprise      │  │
│  └──────────────┘          │  target_risk: 0.10           │  │
│                            └───────────────┬──────────────┘  │
│  ┌──────────────┐                          │                 │
│  │  Policy      │                          │                 │
│  │  Analysis    │─────────────────────────▶│                 │
│  │  System      │                          │                 │
│  └──────────────┘          ┌───────────────▼──────────────┐  │
│                            │        Provider Router        │  │
│                            └───────────────┬──────────────┘  │
│                                            │                 │
│                            ┌───────────────▼──────────────┐  │
│                            │   Ollama (local)              │  │
│                            │   llama3.2 / mistral         │  │
│                            │   NO external connections     │  │
│                            └──────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (audit DB)    Redis (rate limiting)          │ │
│  │  Air-gapped = tamper-evident by physical isolation       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  TrustPlane Dashboard — internal visibility only         │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Configuration

```yaml
provider: ollama
model: mistral:7b
api_key: ${OLLAMA_HOST}        # internal host
target_risk: 0.10              # strict — government context
rate_limit: 10000/day
webhook_url: http://incident-mgmt.internal/trustplane-events
audit_enabled: true
audit_retention_days: 3650     # 10 years
```

---

## Audit trail integrity — air-gap model

In this deployment, audit trail integrity is enforced through infrastructure isolation:

- PostgreSQL runs on a server with no external network access
- No user, process, or service outside the air-gapped network can modify the audit log
- Physical access controls govern the database server
- This is the same integrity model used in defense, classified systems, and critical national infrastructure worldwide

This satisfies EU AI Act Article 12 (record-keeping) without requiring cryptographic append-only structures — the physical boundary is the trust boundary.

For deployments requiring additional cryptographic guarantees, WAL archiving to write-once storage (e.g., tape, WORM drives) can be added as a layer above TrustPlane.

---

## Compliance mapping for public sector

| Requirement | Source | TrustPlane capability |
|---|---|---|
| Risk management | EU AI Act Art. 9 | Epistemic scoring per request |
| Record-keeping | EU AI Act Art. 12 | Immutable audit log (air-gapped) |
| Transparency report | EU AI Act Art. 13 | PDF export on demand |
| Human oversight | EU AI Act Art. 14 | Webhook escalation |
| Data sovereignty | National law | Full air-gap support, local LLM |
| Access control | NIS2 / internal policy | RBAC: admin/operator/auditor/viewer |

---

## What this solves

| Risk | Without TrustPlane | With TrustPlane |
|---|---|---|
| Citizen data leaving national infrastructure | Depends on LLM provider | Impossible — air-gapped Ollama |
| No audit trail for AI decisions | Common in AI deployments | Full trace per request |
| Regulatory non-compliance | High exposure | Article 9/12/13/14 mapped |
| No escalation path for uncertain AI output | Silent failure | ESCALATE → human review |
| Vendor lock-in | Provider-dependent | Swap LLM without changing application |

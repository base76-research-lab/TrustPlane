# CognOS Enterprise — EU AI Act Compliance Guide

## Relevanta artiklar

### Article 13 — Transparency and provision of information to deployers

CognOS Enterprise uppfyller Article 13 genom:

- **Epistemic headers** på varje request: `X-Cognos-Trust-Score`, `X-Cognos-Decision`, `X-Cognos-Trace-Id`
- **Audit export**: `GET /v1/audit/export?format=pdf` genererar Article 13-rapport med attestation-sammanfattning
- **Decision trail**: Varje PASS / REFINE / ESCALATE / BLOCK loggas med trust score, policy och timestamp
- **Retention**: Konfigurerbart via `audit_retention_days` i provider.yaml (default: 90 dagar)

### Article 9 — Risk management system

Trust-scoring-formeln `C = p × (1 − Ue − Ua)` implementerar ett kontinuerligt riskhanteringssystem:
- `p` = prior confidence
- `Ue` = epistemic uncertainty (modellens osäkerhet)
- `Ua` = aleatoric uncertainty (irreducibel brus i data)

Beslutstrappan:
| Trust Score | Beslut    | Åtgärd                          |
|-------------|-----------|----------------------------------|
| ≥ threshold | PASS      | Request tillåten                 |
| threshold − 0.2 | REFINE | Varning i response headers   |
| threshold − 0.4 | ESCALATE | Webhook + loggning           |
| < threshold − 0.4 | BLOCK  | Request nekad (HTTP 403)    |

### Article 12 — Record-keeping

- Alla traces sparas i PostgreSQL med schema-isolation per tenant
- Export: CSV (`/v1/audit/export?format=csv`) och PDF (`?format=pdf`)
- Sökning med tidsintervall: `?from=2024-01-01&to=2024-12-31`

### Article 14 — Human oversight

ESCALATE-beslut triggar webhooks till kundens system, vilket möjliggör mänsklig granskning
innan vidare åtgärd. Konfigureras via `webhook_url` i provider.yaml.

## Audit-rapport

```bash
# Generera PDF-rapport
curl -H "X-API-Key: your-key" \
     -H "X-Cognos-Tenant: your-tenant" \
     "http://localhost:8788/v1/audit/export?format=pdf&from=2024-01-01" \
     -o cognos_audit.pdf

# CSV-export
curl -H "X-API-Key: your-key" \
     "http://localhost:8788/v1/audit/export?format=csv" \
     -o audit.csv
```

## Roller och åtkomstkontroll (RBAC)

| Roll      | Chat | Audit | Admin |
|-----------|------|-------|-------|
| admin     | ✓    | ✓     | ✓     |
| operator  | ✓    | ✗     | ✗     |
| auditor   | ✗    | ✓     | ✗     |
| viewer    | ✗    | ✗     | ✗     |

## Certifiering

CognOS Enterprise är designad för att stödja EU AI Act High-Risk AI system (Annex III)
genom att tillhandahålla:
1. Kontinuerlig riskbedömning per request
2. Spårbarhet via trace IDs
3. Transparenta beslut med epistemic headers
4. Auditloggar med retention policy
5. Human-oversight via webhooks

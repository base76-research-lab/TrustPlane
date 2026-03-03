# TrustPlane — Technical Documentation
**EU AI Act Annex IV — Article 11(1)**

| Field | Value |
|-------|-------|
| Document version | 1.1.0 |
| Date | 2026-03-03 |
| Provider | Base76 Research Lab, Sjöbo, Sweden |
| System name | TrustPlane |
| System version | 1.0.0 |
| Status | Pre-market / Active development |
| Classification assessment | General-purpose AI infrastructure (not Annex III high-risk per se; may serve as infrastructure for high-risk deployers — see §1.4) |

---

## 1. General Description of the AI System

### 1.1 Intended Purpose

TrustPlane is a pluggable LLM (Large Language Model) trust-scoring gateway designed to:

- Proxy LLM API requests from tenant applications to configurable backend providers (Ollama, OpenAI, Anthropic, Groq, Cerebras)
- Score each request with a **trust/risk value** using a deterministic policy engine (`gateway/policy.py`)
- Enforce configurable decision thresholds: `PASS` → `REFINE` → `ESCALATE` → `BLOCK`
- Log all decisions as immutable audit traces per tenant (PostgreSQL, isolated schemas)
- Generate EU AI Act–aligned compliance reports (Articles 9, 12, 13, 14)

**Intended users:** Software operators and enterprises deploying LLM-based products who need audit trails, policy enforcement, and EU AI Act compliance documentation.

**Intended deployment context:** Cloud-hosted API gateway, self-hosted on-premises, or hybrid. Accessed programmatically via REST API. Not intended for direct use by end consumers.

### 1.2 Provider Information

| Field | Value |
|-------|-------|
| Provider name | Base76 Research Lab |
| Address | Sjöbo, Sweden |
| Contact | Björn Wikström |
| GitHub | https://github.com/base76-research-lab/TrustPlane |

### 1.3 System Version History

| Version | Date | Summary of changes |
|---------|------|-------------------|
| 0.9.0 | 2026-02 | Initial release: gateway, audit CSV/PDF export |
| 1.0.0 | 2026-03-03 | Compliance report feature, EU AI Act Article mapping, reports API |
| 1.1.0 | 2026-03-03 | Art. 14 override endpoint, Art. 12 retention enforcement, Art. 73 incident register |
| 1.2.0 | 2026-03-03 | DecisionMandate object in CognosControl; mandate coverage risk area (Art. 9) |

### 1.4 Risk Classification Assessment

TrustPlane is assessed as **not directly high-risk** under Article 6 and Annex III, because it:

- Does not make consequential decisions about natural persons
- Does not perform biometric identification, creditworthiness scoring, recruitment assessment, or any other Annex III use case
- Acts as infrastructure — routing and logging — between a tenant application and an LLM provider

**However:** Tenants deploying TrustPlane in an Annex III context (e.g., HR screening tools, public services, law enforcement support) are themselves subject to high-risk obligations. In such cases, TrustPlane functions as a component in a high-risk AI system, and this documentation is provided to support those tenants' own compliance obligations under Articles 11, 16, and 26.

Pursuant to Article 6(3), this assessment is documented here and will be updated if the system's use cases change materially.

### 1.5 Hardware and Software Requirements

**Runtime requirements:**
- Python 3.12+
- PostgreSQL 14+ (multi-tenant mode) or SQLite (development mode)
- Minimum 1 GB RAM; recommended 2 GB for production
- Network access to configured LLM provider endpoints

**Software dependencies (key):**
- FastAPI — HTTP framework
- asyncpg — PostgreSQL async driver
- reportlab — PDF generation
- pydantic v2 — data validation
- PyYAML — tenant configuration

**Supported LLM providers:**
- Ollama (local, default)
- OpenAI API
- Anthropic Claude API
- Groq API
- Cerebras API

### 1.6 Distribution Format

- Source code repository: GitHub (`base76-research-lab/TrustPlane`)
- Deployment: Docker container or direct Python installation
- API interface: REST/HTTP, OpenAI-compatible `/v1/chat/completions` endpoint

### 1.7 Instructions for Use (Deployers)

Deployers shall:

1. Configure a `provider.yaml` per tenant specifying the LLM provider, model, `target_risk` threshold, and `rate_limit`
2. Set `COGNOS_TIER=enterprise` for full compliance feature access
3. Set `COGNOS_USE_POSTGRES=true` and configure `DATABASE_URL` for persistent audit storage
4. Use the `auditor` or `admin` role for compliance report generation
5. Retrieve compliance reports via `POST /v1/audit/compliance-report` at minimum monthly intervals
6. Retain generated logs and reports for a minimum of **6 months** (Article 12 requirement)
7. Review ESCALATE and BLOCK events via webhook integration within 24 hours
8. Ensure a named human oversight officer is designated per deployment (Article 14)

---

## 2. Detailed Description of Elements and Development Process

### 2.1 System Architecture

```
Tenant Application
        │
        ▼  HTTP (X-API-Key, X-Cognos-Tenant)
┌───────────────────────────────────┐
│         TrustPlane Gateway        │
│                                   │
│  Auth middleware (RBAC)           │
│  Rate limiter                     │
│  ┌─────────────────────────────┐  │
│  │     Policy Engine           │  │
│  │  resolve_decision(mode,     │  │
│  │  target_risk) → decision,   │  │
│  │  risk_score                 │  │
│  └─────────────────────────────┘  │
│           │                       │
│    BLOCK? → 403 immediately       │
│           │                       │
│  ┌────────▼────────────────────┐  │
│  │     LLM Provider Router     │  │
│  │  Ollama / OpenAI / Anthropic│  │
│  │  / Groq / Cerebras          │  │
│  └────────┬────────────────────┘  │
│           │                       │
│  ┌────────▼────────────────────┐  │
│  │     Audit & Trace Store     │  │
│  │  PostgreSQL (per-tenant     │  │
│  │  schema isolation)          │  │
│  └─────────────────────────────┘  │
│                                   │
│  Compliance Report Engine         │
│  (compliance_report.py)           │
└───────────────────────────────────┘
        │
        ▼
  Response + epistemic headers
  (X-Cognos-Decision, X-Cognos-Trust-Score,
   X-Cognos-Trace-Id, X-Cognos-Policy)
```

### 2.2 Policy Engine — Algorithm Logic

File: `gateway/policy.py`

The trust/risk scoring uses a deterministic threshold-based algorithm:

```
base_risk = 0.12 (configurable)
threshold = target_risk (default: 0.5)

if mode == "monitor":        → PASS (all requests pass, fully logged)
if risk ≤ threshold:         → PASS
if risk ≤ threshold + 0.20:  → REFINE (soft warning)
if risk ≤ threshold + 0.40:  → ESCALATE (human review required)
else:                        → BLOCK (request denied, 403)
```

**Design rationale:** The algorithm is intentionally transparent and deterministic. No ML model is used for the core gating decision, ensuring full explainability and reproducibility of every decision. The `trust_score` returned to callers is `1.0 - risk`.

**No training data is used** in the policy engine. It is a rule-based system with configurable thresholds.

### 2.3 Signal Vector

When an LLM provider supports it, the `CognosEnvelope` carries a `SignalVector` with the following fields (all in range [0.0, 1.0]):

| Signal | Description | High value means |
|--------|-------------|-----------------|
| `ue` | Epistemic uncertainty | Model is uncertain / out of knowledge domain |
| `ua` | Aleatoric uncertainty | Irreducible input noise/ambiguity |
| `divergence` | Shadow model divergence | Primary model disagrees with ensemble |
| `citation_density` | Source citation strength | Low = poor verifiability |
| `contradiction` | Internal logical contradiction | High = inconsistent output |
| `out_of_distribution` | OOD detection score | Input unlike training distribution |

### 2.6 Decision Mandate (Art. 9)

An optional `DecisionMandate` object can be included in the `cognos` field of any request. It documents the organisational decision context at the moment of AI invocation — not what the AI does, but why the organisation chose to invoke it.

```json
{
  "cognos": {
    "policy_id": "hr_screening_v2",
    "mandate": {
      "alternatives_considered": ["manual review", "rule-based filter"],
      "uncertainty_accepted": "model may miss edge cases in junior roles",
      "authorized_by": "head_of_hr",
      "decision_context": "Q1 2026 recruitment batch — 120 candidates"
    }
  }
}
```

The mandate is stored in the trace envelope and analysed in the compliance report. If more than 50% of traces in a period lack a mandate, a **Decision Mandate Coverage** risk area is flagged under Art. 9. The `raw_stats.mandate_coverage` field in every report shows coverage rate across the period.

**No system behaviour is changed by the presence or absence of a mandate.** It is purely an audit record.

These signals feed the compliance report risk-area analysis in `enterprise/audit/compliance_report.py`.

### 2.4 Data Flow and Retention

1. **Input data:** Chat messages from tenant application. No personal data is required by TrustPlane; personal data handling is the deployer's responsibility.
2. **Stored per trace:** `trace_id`, `created_at`, `decision`, `policy`, `trust_score`, `risk`, `model`, `is_stream`, `status_code`, `envelope` (full request/response JSON), `metadata`, `expires_at`, `overridden`, `override_by`, `override_at`, `override_reason`
3. **Retention enforcement (Art. 12):** Every trace is stored with `expires_at = created_at + retention_days`. The minimum enforced value is **180 days** (6 months) regardless of tenant configuration. A daily background task (`_retention_purge_loop`) deletes traces whose `expires_at` is in the past. The interval is configurable via `COGNOS_PURGE_INTERVAL_HOURS` (default: 24).
4. **Override audit trail (Art. 14):** When a human reviewer overrides a BLOCK or ESCALATE decision via `POST /v1/traces/{id}/override`, the columns `overridden`, `override_by`, `override_at`, and `override_reason` are set. This record is immutable — a trace can only be overridden once.
5. **Schema isolation:** Each tenant has a dedicated PostgreSQL schema (`tenant_{id}`), preventing cross-tenant data access.

### 2.5 Human Oversight Integration (Article 14)

The system supports human oversight through:

- **ESCALATE decision:** Request is forwarded to the LLM but an immediate webhook notification is dispatched to the deployer's configured endpoint
- **BLOCK decision:** Request is denied with HTTP 403; webhook notification dispatched
- **Compliance reports:** Structured risk analysis surfaces patterns requiring human review
- **Audit export:** Full trace export (CSV/PDF) for human auditor review
- **RBAC roles:** `auditor` role provides read-only access to traces and reports without ability to modify system behaviour

**Override endpoint (v1.1.0):** `POST /v1/traces/{trace_id}/override` allows a named auditor or admin to mark a BLOCK or ESCALATE trace as human-reviewed. The override is persisted with `override_by`, `override_at`, and `override_reason`, creating a full audit trail of human oversight decisions per Article 14.

### 2.6 Testing and Validation

- Smoke test suite: `tests/test_smoke.py`
- Test environment: SQLite fallback mode (`COGNOS_USE_POSTGRES=false`)
- Validation of policy engine: unit-testable via `resolve_decision()` with deterministic input/output
- Compliance report validation: `analyze_risk_areas()` is fully deterministic and unit-testable

**Known limitation:** No adversarial input testing or bias evaluation has been performed in v1.0.0. This is documented as a gap and planned for v1.1.0.

---

## 3. Monitoring, Functioning and Control

### 3.1 Performance Capabilities and Limitations

| Capability | Status |
|------------|--------|
| Multi-tenant isolation | Supported (PostgreSQL schemas) |
| Decision throughput | Limited by downstream LLM provider latency |
| Audit log completeness | 100% of proxied requests are logged |
| Compliance report coverage | All 6 signal dimensions; requires signal data in trace envelope |
| Free tier rate limit | 100 requests/day |
| Enterprise tier rate limit | Configurable (default: 1000/day) |

**Limitations:**
- Signal vector values (`ue`, `ua`, `divergence` etc.) are only populated if the upstream LLM provider or the caller injects them in the `cognos.signals` field. If not present, compliance reports will not flag signal-based risk areas — only escalation rate will be analysed.
- The system does not analyse message *content* for bias, harmful content, or factual accuracy. Content moderation is outside TrustPlane's scope and must be handled by the deployer or the LLM provider.
- `base_risk` is currently a static value (0.12). Dynamic risk scoring from message content is not implemented.

### 3.2 Anticipated Unintended Outcomes

| Scenario | Risk | Mitigation |
|----------|------|-----------|
| High false positive rate (BLOCK on safe requests) | Deployer trust erosion | Configurable `target_risk` per tenant; `monitor` mode available |
| Signal data not populated → silent compliance gaps | Incomplete risk assessment | Report explicitly states "no signal data" when signals are missing |
| PostgreSQL unavailable at startup | SQLite fallback (no tenant isolation) | Log warning at startup; deployers warned in documentation |
| API key compromise | Unauthorised trace access | Keys are hashed; rotation documented; RBAC limits blast radius |

### 3.3 Input Data Specifications

TrustPlane accepts any valid OpenAI-compatible chat completion request. Input requirements:

- `messages`: array of `{role, content}` objects
- `model`: string identifier for the target LLM
- `cognos` (optional): control object with `mode`, `policy_id`, `target_risk`, `signals`
- Authentication: `X-API-Key` header (required)

TrustPlane does **not** impose restrictions on message content at the input layer. Content policy enforcement is the deployer's responsibility.

---

## 4. Performance Metrics

The following metrics are appropriate for TrustPlane's intended function as an audit and policy gateway:

| Metric | Description | Target |
|--------|-------------|--------|
| Decision accuracy | % of BLOCK/ESCALATE decisions that were appropriate | Evaluated per tenant via compliance report review |
| Escalation rate | (ESCALATE + BLOCK) / total requests | Alert threshold: > 15% (Article 14 trigger) |
| Audit completeness | % of requests with a stored trace | 100% (by design) |
| Signal coverage | % of traces with populated signal vector | Dependent on deployer integration |
| Report generation time | Time to generate compliance report | < 5 seconds for ≤ 10,000 traces |
| Avg epistemic uncertainty | Mean `ue` across period | Alert threshold: > 0.30 |
| Avg model divergence | Mean `divergence` across period | Alert threshold: > 0.20 |

Metric thresholds are derived from the signal-analysis logic in `enterprise/audit/compliance_report.py` (`_THRESHOLDS` dictionary) and map directly to EU AI Act article obligations.

---

## 5. Risk Management System (Article 9)

### 5.1 Identified Risks

| Risk ID | Description | Likelihood | Impact | Mitigation |
|---------|-------------|-----------|--------|-----------|
| R-01 | Incorrect BLOCK of legitimate request | Medium | Medium | `monitor` mode; configurable threshold; override planned (v1.1) |
| R-02 | False PASS of harmful request | Low | High | Deployer content policy; LLM provider safety filters |
| R-03 | Audit log loss (DB failure) | Low | High | PostgreSQL replication recommended; startup warning if unavailable |
| R-04 | API key leakage | Low | High | RBAC; key rotation; env-based secret management |
| R-05 | Compliance report misinterpretation | Medium | Medium | Report includes explanation + recommendation text per risk area |
| R-06 | Signal data absent → incomplete report | High | Medium | Report documents explicitly when signals are missing |
| R-07 | Deployer uses system in high-risk context without declaring it | Medium | High | This documentation; deployer onboarding checklist (planned) |
| R-08 | Retention policy not configured by deployer | Medium | Medium | Default 90 days documented; 6-month minimum stated in instructions |

### 5.2 Residual Risks

The following residual risks are accepted in v1.0.0 with documented mitigations planned:

- **No override API** (R-01 mitigation incomplete) — planned v1.1.0
- **No adversarial input testing** — planned v1.1.0
- **No content-level analysis** — out of scope; deployer responsibility

### 5.3 Risk Review Schedule

The risk register shall be reviewed at:
- Each major version release
- Following any serious incident (Article 73)
- At minimum annually

---

## 6. Changes Through Lifecycle

| Version | Change | Compliance impact |
|---------|--------|------------------|
| 0.9.0 → 1.0.0 | Added compliance report engine, reports API, EU AI Act Article mapping | Expanded Art. 9, 12, 13, 14 coverage |
| 1.0.0 → 1.1.0 (planned) | Override endpoint, retention enforcement, adversarial testing | Art. 14 gap closure |
| 1.1.0 → 1.2.0 (planned) | Dynamic risk scoring, content signal integration | Art. 9, 15 improvement |

All changes to the policy engine (`gateway/policy.py`) or signal thresholds (`compliance_report.py`) constitute **material changes** requiring this document to be updated before deployment.

---

## 7. Harmonised Standards and Compliance Solutions

No EU harmonised standards have been formally adopted for AI systems of this type as of 2026-03-03.

The following standards and frameworks are applied or referenced:

| Standard / Framework | Application |
|---------------------|------------|
| ISO/IEC 42001:2023 (AI Management Systems) | Structural reference for QMS (see `QUALITY_MANAGEMENT.md`, planned) |
| ISO/IEC 27001 | Information security principles applied to key management and tenant isolation |
| OWASP Top 10 for LLM Applications | Security review baseline for API design |
| NIST AI RMF (AI Risk Management Framework) | Risk identification methodology |
| EU AI Act Regulation (EU) 2024/1689 | Primary compliance framework |

The CognOS trust-scoring formula `C = p · (1 − Ue − Ua)` (Base76 Research Lab internal) is the theoretical basis for the signal-based risk analysis. It is documented in the FNC research trilogy (Applied-Ai-Philosophy GitHub organisation).

---

## 8. EU Declaration of Conformity

*This section will be completed upon formal conformity assessment prior to commercial placement on the EU market.*

As of v1.0.0, TrustPlane is in active development and pre-market evaluation. A self-assessment (internal control, Annex VI pathway) is the planned conformity route given the system's infrastructure nature and the absence of applicable harmonised standards mandating third-party assessment.

The provider (Base76 Research Lab) declares that TrustPlane v1.0.0 is designed with the intent to comply with EU AI Act requirements applicable to its classification, and that this technical documentation is maintained and updated in accordance with Article 11.

---

## 9. Post-Market Monitoring Plan (Article 72)

### 9.1 Monitoring Mechanisms

| Mechanism | Frequency | Responsible |
|-----------|-----------|-------------|
| Compliance report generation | Monthly per active tenant | Tenant auditor / admin |
| Risk area threshold review | Quarterly | Base76 Research Lab |
| Serious incident assessment | Per incident (within 15 days) | Provider + Deployer |
| Signal threshold calibration review | Per major release | Base76 Research Lab |
| Tenant feedback collection | Ongoing | Base76 Research Lab |

### 9.2 Serious Incident Reporting (Article 73)

A **serious incident** for TrustPlane is defined as:

- Systematic failure to log audit traces (breach of Article 12)
- Policy engine producing incorrect decisions at scale (> 5% of requests) due to a bug
- Unauthorised access to tenant trace data
- Use of the system in a high-risk context leading to documented harm to a natural person

In the event of a serious incident, Base76 Research Lab shall:

1. Identify and contain the incident within 24 hours
2. Notify affected tenants within 48 hours
3. Report to the relevant national supervisory authority (Sweden: IMY — Integritetsskyddsmyndigheten) within 15 days if the incident involves personal data or fundamental rights impact
4. Document the incident in the incident register (`docs/incidents/`) using the provided template
5. Update this technical documentation with the incident summary and corrective action

### 9.3 Performance Threshold Alerts

The following conditions in a monthly compliance report shall trigger a provider-level review:

- Overall risk level `HIGH` in any tenant report
- Any risk area with `severity: high` affecting > 20% of traces
- Escalation rate > 30% across any tenant in a 30-day period

---

## Appendix A — File Structure (v1.1.0)

```
Cognos-enterprise/
├── enterprise/
│   ├── app.py                    # FastAPI application, all endpoints
│   ├── tier.py                   # Feature gating (free / enterprise)
│   ├── audit/
│   │   ├── exporter.py           # CSV + raw PDF export
│   │   └── compliance_report.py  # EU AI Act compliance report engine
│   ├── auth/
│   │   ├── middleware.py         # API key auth, RBAC
│   │   └── rate_limit.py         # Rate limiting
│   ├── config/
│   │   └── loader.py             # provider.yaml loader with env expansion
│   ├── providers/                # LLM provider adapters
│   │   ├── ollama.py
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   ├── groq.py
│   │   └── cerebras.py
│   ├── tenants/
│   │   └── router.py             # PostgreSQL multi-tenant store + override + purge
│   └── webhooks/
│       └── dispatcher.py         # Webhook dispatch on ESCALATE/BLOCK
├── gateway/
│   ├── models.py                 # Pydantic data models (SignalVector etc.)
│   ├── policy.py                 # Deterministic trust/risk policy engine
│   ├── reports.py                # Basic trust report builder
│   └── trace_store.py            # SQLite fallback store
├── docs/
│   └── incidents/
│       ├── README.md             # Incident register log + classification (Art. 73)
│       └── TEMPLATE.md           # Incident report template
├── TECHNICAL_DOCUMENTATION.md   # This document (Annex IV, Art. 11)
├── QUALITY_MANAGEMENT.md         # QMS document (Art. 17)
└── tests/
    └── test_smoke.py
```

---

## Appendix B — API Endpoints Summary

| Method | Path | Auth | Art. | Description |
|--------|------|------|------|-------------|
| POST | `/v1/chat/completions` | operator/admin | — | LLM proxy with trust scoring |
| GET | `/v1/audit/export` | auditor/admin | 12 | CSV or raw PDF trace export |
| POST | `/v1/audit/compliance-report` | auditor/admin | 9,12,13,14 | Generate EU AI Act compliance report (JSON or PDF) |
| GET | `/v1/reports/` | auditor/admin | 12 | List saved compliance reports |
| GET | `/v1/reports/{id}` | auditor/admin | 12 | Fetch compliance report JSON |
| GET | `/v1/reports/{id}/pdf` | auditor/admin | 12,13 | Download compliance report PDF |
| GET | `/v1/traces/{id}` | auditor/admin | 12 | Fetch single trace record |
| POST | `/v1/traces/{id}/override` | auditor/admin | 14 | Mark BLOCK/ESCALATE trace as human-reviewed; records override_by, override_at, override_reason |
| POST | `/v1/signup` | public | — | Register new tenant |
| GET | `/v1/tier` | operator/admin | — | Tier and feature info |
| GET | `/healthz` | public | — | Health check |

---

---

## Appendix C — Database Schema (v1.1.0)

### `tenant_{id}.traces`

| Column | Type | Description |
|--------|------|-------------|
| `trace_id` | TEXT PK | Unique trace identifier (`tr_…`) |
| `created_at` | TIMESTAMPTZ | Request timestamp |
| `decision` | TEXT | `PASS` / `REFINE` / `ESCALATE` / `BLOCK` |
| `policy` | TEXT | Policy ID used |
| `trust_score` | DOUBLE PRECISION | `1.0 - risk` |
| `risk` | DOUBLE PRECISION | Risk score [0.0–1.0] |
| `is_stream` | BOOLEAN | Streaming request flag |
| `status_code` | INTEGER | HTTP response code |
| `model` | TEXT | LLM model identifier |
| `request_fp` | JSONB | Request fingerprint |
| `response_fp` | JSONB | Response fingerprint |
| `envelope` | JSONB | Full request/response + cognos signals |
| `metadata` | JSONB | Arbitrary tenant metadata |
| `expires_at` | TIMESTAMPTZ | Retention expiry (Art. 12); min 180 days from `created_at` |
| `overridden` | BOOLEAN | True if human-reviewed via override endpoint (Art. 14) |
| `override_by` | TEXT | Role + API key suffix of reviewer |
| `override_at` | TIMESTAMPTZ | Timestamp of override |
| `override_reason` | TEXT | Mandatory human-provided justification |

### `tenant_{id}.reports`

| Column | Type | Description |
|--------|------|-------------|
| `report_id` | TEXT PK | Unique report identifier (`rpt_…`) |
| `created_at` | TIMESTAMPTZ | Report generation timestamp |
| `period_from` | TIMESTAMPTZ | Analysis period start |
| `period_to` | TIMESTAMPTZ | Analysis period end |
| `risk_level` | TEXT | `LOW` / `MEDIUM` / `HIGH` |
| `summary_json` | JSONB | Full `ComplianceReport` as JSON |
| `pdf_blob` | BYTEA | PDF binary (enterprise tier only) |

---

*Document maintained by Base76 Research Lab. Next scheduled review: 2026-06-01 (or on material system change, whichever comes first).*

# TrustPlane — Quality Management System
**EU AI Act Article 17 | ISO/IEC 42001 reference alignment**

| Field | Value |
|-------|-------|
| Document version | 1.1.0 |
| Date | 2026-03-03 |
| Provider | Base76 Research Lab, Sjöbo, Sweden |
| System | TrustPlane v1.1.0 |
| QMS owner | Björn Wikström |
| Next review | 2026-06-01 |

---

## 1. Scope and Purpose

This document establishes the Quality Management System (QMS) for TrustPlane in accordance with **EU AI Act Article 17**. It covers the full lifecycle of the system — from design and development through deployment, monitoring, and decommissioning.

The QMS applies to:
- Base76 Research Lab as provider
- All versions of TrustPlane placed on the market or put into service
- All tenants using TrustPlane as infrastructure for AI-assisted decisions

Reference standards: ISO/IEC 42001:2023 (AI Management Systems), prEN 18286 (draft, anticipated 2026).

---

## 2. Compliance Strategy (Art. 17.1.a)

### 2.1 Regulatory posture

TrustPlane is designed to comply with EU AI Act Regulation (EU) 2024/1689. The compliance strategy is:

1. **Self-assessment pathway** (Annex VI) — as infrastructure software without direct Annex III high-risk classification, internal control is the applicable conformity route
2. **Documentation-first** — all design decisions, risk assessments, and changes are documented before deployment
3. **Transparency by default** — every API response carries epistemic headers; every decision is logged
4. **Conservative thresholds** — default `target_risk: 0.5` errs towards escalation rather than silent pass

### 2.2 Regulatory monitoring

Base76 Research Lab monitors:
- EU AI Act delegated acts and Commission guidelines (via EUR-Lex)
- Harmonised standard developments (prEN 18286, ISO/IEC 42001 updates)
- Guidance from the European AI Office and national supervisory authorities

Regulatory changes that affect TrustPlane's compliance obligations shall trigger a QMS review within 30 days of publication.

---

## 3. Design and Development Procedures (Art. 17.1.b)

### 3.1 Development workflow

All code changes follow this process:

| Stage | Activity | Artefact |
|-------|----------|---------|
| Design | Architectural decision documented in issue/PR | GitHub issue |
| Implementation | Code written, self-reviewed | Pull request |
| Review | Code review before merge to `main` | PR approval |
| Testing | Smoke tests + manual verification | `tests/test_smoke.py` |
| Documentation | `TECHNICAL_DOCUMENTATION.md` updated if material change | Commit |
| Deployment | Tagged release | Git tag + GitHub release |

### 3.2 Definition of material change

The following constitute **material changes** requiring a QMS and technical documentation review before deployment:

- Any change to `gateway/policy.py` (policy engine logic)
- Any change to signal thresholds in `enterprise/audit/compliance_report.py` (`_THRESHOLDS`)
- Addition of new LLM provider adapters
- Changes to the data schema (`tenants/router.py` — `traces` or `reports` tables)
- Changes to authentication or RBAC logic (`auth/middleware.py`)
- New endpoints that expose personal data or audit records

### 3.3 Branching and versioning

- `main` — production-ready, tagged releases only
- Feature branches — all development work
- Semantic versioning: `MAJOR.MINOR.PATCH`
  - MAJOR: breaking API changes or policy engine redesign
  - MINOR: new features, new endpoints, new providers
  - PATCH: bug fixes, documentation updates

---

## 4. Testing and Validation Procedures (Art. 17.1.c)

### 4.1 Test coverage

| Test type | Tool | Scope | Status |
|-----------|------|-------|--------|
| Smoke tests | pytest | Startup, basic endpoints, policy engine | `tests/test_smoke.py` ✅ |
| Policy engine unit tests | pytest | `resolve_decision()` boundary conditions | Planned v1.1.0 |
| Compliance report unit tests | pytest | `analyze_risk_areas()` signal thresholds | Planned v1.1.0 |
| Integration tests | pytest + test DB | Full request lifecycle | Planned v1.1.0 |
| Adversarial input tests | TBD | Policy bypass attempts | Planned v1.1.0 |
| Load tests | locust/k6 | Throughput under concurrent tenants | Planned v1.2.0 |

### 4.2 Validation criteria

A release is considered validated when:
- All smoke tests pass
- No regressions in audit logging (100% trace coverage verified)
- Compliance report generation tested with synthetic trace data covering all 6 signal dimensions
- `TECHNICAL_DOCUMENTATION.md` reflects the release state

### 4.3 Known test gaps (v1.1.0)

- No adversarial input testing
- No bias evaluation
- No load testing under multi-tenant concurrent access

These are documented in `TECHNICAL_DOCUMENTATION.md §2.6` and scheduled for v1.2.0.

---

## 5. Technical Specifications (Art. 17.1.d)

Technical specifications are maintained in:

| Document | Content |
|----------|---------|
| `TECHNICAL_DOCUMENTATION.md` | Full Annex IV documentation |
| `gateway/models.py` | Canonical data model (Pydantic) |
| `enterprise/app.py` | API contract (FastAPI auto-docs at `/docs`) |
| `enterprise/config/provider.yaml` | Tenant configuration schema |

The FastAPI application exposes interactive API documentation at `/docs` (Swagger UI) and `/redoc` in all deployments.

---

## 6. Data Governance (Art. 17.1.e)

### 6.1 Data categories handled

| Data category | Where stored | Retention | Access control |
|--------------|-------------|---------|---------------|
| Audit traces (decision, trust_score, model, timestamp, override data) | PostgreSQL `tenant_{id}.traces` | Min 180 days enforced in code; `expires_at` set per trace | auditor, admin roles |
| Request envelope (full request/response JSON) | PostgreSQL `envelope` JSONB column | Same as traces | admin role |
| Human override records (override_by, override_at, override_reason) | PostgreSQL `tenant_{id}.traces` — same row | Same as traces | auditor, admin roles |
| Compliance reports (JSON + PDF) | PostgreSQL `tenant_{id}.reports` | Indefinite until manual deletion | auditor, admin roles |
| API keys | In-process store (env-seeded) | Session lifetime | admin only |

### 6.2 Personal data

TrustPlane does not require personal data to function. The `envelope` column may contain personal data if the tenant's users include it in chat messages. This is:

- The deployer's responsibility to assess under GDPR
- Not processed by TrustPlane for any purpose beyond logging
- Subject to the deployer's own data retention and deletion policies

**Recommendation to deployers:** Configure `retention: "fingerprints"` in `CognosControl` to store only content fingerprints rather than full message content where personal data is expected.

### 6.3 Tenant isolation

Each tenant's data is isolated in a dedicated PostgreSQL schema (`tenant_{id}`). Cross-schema access is prevented at the application layer (tenant_id bound to API key) and at the database layer (schema separation). No shared tables exist between tenants.

---

## 7. Risk Management (Art. 17.1.f)

Risk management is conducted per the process defined in `TECHNICAL_DOCUMENTATION.md §5`. This QMS requires:

- Risk register reviewed at each major release
- New risks identified during development added to the register before the release is tagged
- Risks rated on likelihood × impact (Low/Medium/High)
- Each risk assigned a mitigation owner (default: Björn Wikström)

Current risk register: `TECHNICAL_DOCUMENTATION.md §5.1`.

---

## 8. Post-Market Monitoring (Art. 17.1.g)

Post-market monitoring is defined in `TECHNICAL_DOCUMENTATION.md §9`. This QMS requires:

- **Monthly:** Compliance report generated per active tenant and reviewed by the tenant's designated auditor
- **Quarterly:** Base76 Research Lab reviews aggregated signal threshold performance across all tenants and adjusts default thresholds if evidence warrants
- **Per incident:** Serious incident process initiated (see §10 below)

The compliance report engine (`enterprise/audit/compliance_report.py`) is the primary monitoring instrument. It is deterministic, auditable, and generates no false positives — a risk area is flagged if and only if the measured signal average crosses the documented threshold.

---

## 9. Incident Reporting (Art. 17.1.h)

### 9.1 Incident classification

| Class | Definition | Response time |
|-------|-----------|--------------|
| Critical | Audit log failure, data breach, systematic incorrect decisions | 24 hours containment, 48 hours tenant notification |
| Major | Single-tenant report generation failure, provider routing failure | 72 hours resolution |
| Minor | Documentation gap, non-material config error | Next release cycle |

### 9.2 Serious incident process (Article 73)

1. Incident detected (automated alert or tenant report)
2. Severity classified by QMS owner
3. If Critical: containment action within 24 hours
4. Tenant notified within 48 hours
5. If personal data or fundamental rights impact: report to **IMY** (Integritetsskyddsmyndigheten, Sweden) within 15 days
6. Root cause analysis documented in `docs/incidents/` using `TEMPLATE.md`
7. Corrective action implemented and verified
8. `TECHNICAL_DOCUMENTATION.md` §9.2 updated with incident summary

### 9.3 Incident register

Incidents are logged in `docs/incidents/` — one file per incident named `YYYY-MM-DD-<slug>.md`. The register index is maintained in `docs/incidents/README.md`.

Each entry (per `docs/incidents/TEMPLATE.md`) includes:
- Incident ID, date, class, affected tenants
- IMY report status
- Description, impact, root cause
- Containment and corrective actions with owners and target dates
- Lessons learned

---

## 10. Communication Procedures (Art. 17.1.i)

| Communication type | Channel | Trigger |
|-------------------|---------|---------|
| Critical incident → tenants | Direct (email/webhook) | Within 48 hours of detection |
| Release notes | GitHub Releases | Each tagged release |
| API breaking changes | GitHub Releases + 30-day deprecation notice | Before MAJOR version |
| Regulatory material changes | GitHub Releases + this document update | Within 30 days of publication |
| Compliance report availability | API (`GET /v1/reports/`) | Continuous |

---

## 11. Record-Keeping (Art. 17.1.j)

| Record type | Location | Retention |
|------------|---------|---------|
| Technical documentation | `TECHNICAL_DOCUMENTATION.md` (git history) | Indefinite |
| This QMS document | `QUALITY_MANAGEMENT.md` (git history) | Indefinite |
| Audit traces | PostgreSQL per tenant | Min 6 months (Art. 12) |
| Compliance reports | PostgreSQL per tenant + PDF | Indefinite until deleted |
| Incident register | `/docs/incidents/` | Indefinite |
| Git commit history | GitHub `main` branch | Indefinite |

All documents are version-controlled via Git. Every material change is traceable to a specific commit with author, date, and description.

---

## 12. Resource Management (Art. 17.1.k)

| Resource | Allocation |
|---------|-----------|
| QMS owner | Björn Wikström (100% responsible for compliance) |
| Development | Base76 Research Lab |
| Infrastructure | Provider's or tenant's cloud/on-premises environment |
| Compliance tooling | TrustPlane itself (self-hosting the compliance report engine) |
| External review | Planned: legal review of conformity declaration before EU commercial launch |

Competence requirements for QMS owner:
- Working knowledge of EU AI Act (Regulation 2024/1689)
- Understanding of TrustPlane architecture and policy engine
- Ability to interpret compliance reports and act on findings

---

## 13. Accountability Framework (Art. 17.1.l)

| Role | Responsibility | Person |
|------|---------------|--------|
| Provider / QMS owner | Overall compliance, documentation, incident response | Björn Wikström, Base76 Research Lab |
| Deployer (tenant admin) | Correct deployment configuration, human oversight designation, 6-month log retention | Tenant's designated admin |
| Deployer (tenant auditor) | Monthly compliance report review, escalation review | Tenant's designated auditor |
| Human oversight officer | Review ESCALATE/BLOCK events; use `POST /v1/traces/{id}/override` to document approval with mandatory reason | Named per deployment by tenant |

Deployers accept accountability for their deployment configuration upon API key issuance. Base76 Research Lab provides the infrastructure and documentation; the deployer is responsible for its contextual use.

---

## Appendix — Article 17 Compliance Checklist

| Art. 17.1 sub-item | Covered in | Status |
|---------------------|-----------|--------|
| (a) Compliance strategy | §2 | ✅ |
| (b) Design and development procedures | §3 | ✅ |
| (c) Testing and validation | §4 | ✅ (gaps noted) |
| (d) Technical specifications | §5 | ✅ |
| (e) Data management | §6 | ✅ |
| (f) Risk management | §7 + TECHNICAL_DOCUMENTATION §5 | ✅ |
| (g) Post-market monitoring | §8 + TECHNICAL_DOCUMENTATION §9 | ✅ |
| (h) Incident reporting | §9 | ✅ |
| (i) Communication | §10 | ✅ |
| (j) Record-keeping | §11 | ✅ |
| (k) Resource management | §12 | ✅ |
| (l) Accountability | §13 | ✅ |

---

*Maintained by Base76 Research Lab. Changes to this document require a git commit with rationale. Next scheduled review: 2026-06-01.*

# TrustPlane: Epistemic Trust Scoring for Production AI Systems

**A Technical and Strategic Whitepaper**

*Base76 Research Lab — Björn Wikström*
*Version 1.0 — March 2026*

---

## Executive summary

Organizations deploying large language models in production face a category of operational risk with no established mitigation infrastructure: the unverified AI response. Every LLM output that reaches a user without a documented confidence assessment is an undocumented decision — invisible to compliance, unauditable under regulation, and undefended against liability.

TrustPlane is an AI Trust Control Plane that intercepts LLM requests, scores them for epistemic uncertainty before the response reaches the user, and enforces a configurable risk policy. Every decision is logged, exportable, and mapped to EU AI Act requirements.

This paper describes the theoretical foundation, the implementation model, the deployment architecture, and the evidence basis for the scoring approach.

---

## 1. The problem: unverified AI in regulated environments

The deployment of LLMs in production has outpaced the development of governance infrastructure. The pattern is consistent across industries: a model is integrated, performs well in testing, and is deployed — without any systematic mechanism for detecting when it is operating outside its competence.

The failure modes are not edge cases. They are properties of the technology:

- **Hallucination** — a model generates plausible but false outputs with no signal to the receiving system
- **Out-of-distribution requests** — a model encounters a domain it was not trained on and responds with calibrated-sounding uncertainty it does not actually possess
- **Alignment failure under distribution shift** — a model behaves correctly on average but fails in specific subpopulations of requests

The consequence in regulated industries is direct: a hallucinated clinical reference, a fabricated legal citation, or an incorrect financial calculation that enters a downstream system without review is a compliance failure, a liability event, and in some jurisdictions a regulatory violation.

The EU AI Act (Regulation 2024/1689) formalizes this concern. High-risk AI systems (Annex III) are required to implement risk management (Article 9), maintain records (Article 12), provide transparency documentation (Article 13), and ensure human oversight mechanisms (Article 14). None of these requirements can be met by a system that has no visibility into the confidence of its own outputs.

---

## 2. Theoretical foundation: the epistemic trust formula

TrustPlane's scoring model is grounded in epistemic probability theory and the Field-Node-Cockpit (FNC) framework developed at Base76 Research Lab.

### 2.1 The formula

```
C = p × (1 − Ue − Ua)
```

**C** — Trust score ∈ [0, 1]. The confidence that a given response is reliable enough to forward without human review.

**p** — Prior confidence. The baseline probability that a request of this type, from this model, in this domain, will be answered correctly. In the current implementation this is a configurable baseline (`base_risk = 0.12` by default, yielding `p = 0.88`). Domain-specific calibration is addressed in Section 4.

**Ue** — Epistemic uncertainty. The reducible component of uncertainty — what the model does not know, but could in principle know. High Ue indicates the model is operating at the edge of its training distribution. This is the uncertainty that human review can address.

**Ua** — Aleatoric uncertainty. The irreducible component — noise inherent in the domain that no model, and no human reviewer, can eliminate. High Ua indicates the request itself is inherently ambiguous.

### 2.2 Research basis

The formula is an application of the uncertainty decomposition established in the CognOS epistemic reasoning framework (Wikström, 2025). The separation of epistemic and aleatoric uncertainty is a standard decomposition in Bayesian epistemology; the contribution of the CognOS framework is its operationalization as a runtime policy signal.

Directly relevant publications:

- *When Alignment Reduces Uncertainty: Epistemic Variance Collapse and Its Implications for Metacognitive AI* (Wikström, 2026) — DOI: [10.5281/zenodo.18731535](https://doi.org/10.5281/zenodo.18731535)
- *Applied AI Philosophy: A Field-Defining Paper* (Wikström, 2025) — DOI: [10.5281/zenodo.17722837](https://doi.org/10.5281/zenodo.17722837)
- *Epistemic Circuit Dynamics in Neural Architectures* (Wikström, 2026) — DOI: [10.5281/zenodo.18756421](https://doi.org/10.5281/zenodo.18756421)

The open-source scoring engine: [cognos-proof-engine](https://github.com/base76-research-lab/cognos-proof-engine) (MIT)

### 2.3 The decision taxonomy

The trust score is mapped to a four-outcome policy:

```
C ≥ threshold              →  PASS      Forward request
C ≥ threshold − 0.2        →  REFINE    Forward with warning headers
C ≥ threshold − 0.4        →  ESCALATE  Trigger human review webhook
C < threshold − 0.4        →  BLOCK     Reject request, save trace
```

The threshold is configurable per tenant (`target_risk` in provider.yaml). A medical system may set `target_risk: 0.05` — escalating any request where confidence falls below 95%. A lower-risk customer service deployment may accept `target_risk: 0.4`.

This is a testable, falsifiable model. A system calibrated to `target_risk: 0.3` should escalate measurably more than one set to `target_risk: 0.7`. The difference is loggable, exportable, and auditable against actual outcomes.

---

## 3. What is implemented — honestly

Transparency about the current state of implementation is a prerequisite for trust in a trust-scoring system.

### 3.1 What is fully implemented

- Policy enforcement: the four-outcome decision taxonomy is implemented and enforced in the gateway
- Trace logging: every request produces an immutable trace with trace ID, decision, trust score, policy, model, and timestamp
- Audit export: CSV and PDF (EU AI Act Article 13 format) on demand
- Webhook dispatch: ESCALATE and BLOCK events trigger configurable webhooks with retry logic
- Multi-tenant isolation: PostgreSQL schema-per-tenant
- Provider routing: Ollama, OpenAI, Anthropic, Groq, Cerebras
- RBAC: admin / operator / auditor / viewer roles
- Rate limiting: Redis-backed token bucket per tenant

### 3.2 Current limitations and roadmap

**Prior calibration (`p`):**
The current implementation uses a configurable `base_risk` parameter (default: 0.12). This is a reasonable baseline for general-purpose deployments but does not adapt to domain-specific failure rates. Planned: domain-specific calibration API, allowing operators to update `p` based on observed outcomes in their deployment.

**Dynamic Ue/Ua extraction:**
In the current implementation, Ue and Ua are not extracted from individual model outputs — the formula operates on the baseline risk and threshold. The decision taxonomy provides policy enforcement and audit logging at full fidelity today. Dynamic per-response uncertainty extraction (via token log-probabilities or ensemble sampling) is on the research roadmap and will be documented in a future version of the CognOS engine.

**Audit trail immutability:**
PostgreSQL is not cryptographically append-only by default. TrustPlane addresses this in two ways: (a) in air-gapped deployments, physical and network isolation enforces tamper-evidence without cryptographic controls — the same model used in defense and public sector infrastructure; (b) for deployments requiring cryptographic guarantees, WAL archiving to write-once storage (WORM, tape) can be layered above the database. Native cryptographic append-only support (Merkle-tree attestation) is on the roadmap.

---

## 4. Architecture

```
Your Application
      │
      ▼
TrustPlane Gateway          trust scoring · policy enforcement
      │                     RBAC · rate limiting · audit logging
      │                     webhook dispatch · tenant isolation
      │
      ▼
Provider Router
      │
      ├── Ollama             on-premise, air-gapped
      ├── OpenAI
      ├── Anthropic          Claude Sonnet / Opus / Haiku
      ├── Groq
      └── Cerebras

PostgreSQL                  per-tenant audit trail
Redis                       rate limiting
Dashboard                   visibility layer (Next.js)
MCP Server                  Claude Code integration
```

### 4.1 Air-gapped deployment

For sovereign, defense, and regulated healthcare deployments, TrustPlane runs entirely within an air-gapped network alongside a local Ollama instance. No request data, no audit log, and no configuration leaves the network boundary. This is the deployment model for organizations with data residency requirements, national security constraints, or where patient/citizen data must not traverse external networks.

### 4.2 SaaS deployment

Multi-tenant SaaS with PostgreSQL schema-per-tenant isolation. No data is shared between tenants at any layer.

---

## 5. EU AI Act compliance mapping

| Article | Requirement | TrustPlane implementation |
|---|---|---|
| Art. 9 | Risk management system throughout lifecycle | Epistemic scoring on every inference, configurable threshold per tenant |
| Art. 12 | Record-keeping for high-risk systems | Immutable trace log: trace ID, decision, score, policy, model, timestamp |
| Art. 13 | Transparency to deployers | Automated Article 13 PDF report, exportable on demand |
| Art. 14 | Human oversight measures | ESCALATE webhook — human review triggered before downstream action |
| Art. 17 | Quality management system | Audit trail, RBAC, policy versioning |

Full compliance documentation: [docs/EU_AI_ACT.md](EU_AI_ACT.md)

---

## 6. Deployment scenarios

Three representative deployments are documented in detail:

**Healthcare — Clinical documentation (air-gapped)**
`target_risk: 0.05`. Every clinical note scored before EHR entry. Ambiguous inputs escalated to physician review. Ollama on-premise — no patient data leaves the hospital network. Full scenario: [docs/scenarios/healthcare.md](scenarios/healthcare.md)

**Legal — Contract analysis (Anthropic backend)**
`target_risk: 0.15`. Complex jurisdiction clauses return REFINE. Novel instruments trigger ESCALATE to partner review queue. Seven-year audit retention. Full scenario: [docs/scenarios/legal.md](scenarios/legal.md)

**Public sector — Sovereign deployment**
`target_risk: 0.10`. Air-gapped, national data sovereignty, Ollama local. Full EU AI Act + NIS2 compliance mapping. Full scenario: [docs/scenarios/public-sector.md](scenarios/public-sector.md)

---

## 7. Pricing and engagement models

| Tier | Description | Pricing |
|---|---|---|
| Free | OSS core (cognos-proof-engine), 1 tenant, 100 req/day, CSV export | Open source (MIT) |
| SaaS | Hosted, full enterprise feature set, managed infrastructure | From €499/month per tenant |
| Self-hosted license | On-premise, air-gap compatible, full source access | From €25,000/year |
| Enterprise consulting | Architecture review, policy calibration, compliance documentation | Contact |

Healthcare, defense, and public sector deployments typically require the self-hosted license or consulting engagement.

Contact: [bjorn@base76.se](mailto:bjorn@base76.se)

---

## 8. About Base76 Research Lab

Base76 Research Lab is an independent AI research organization based in Sjöbo, Sweden, focused on epistemic AI — systems that know what they don't know.

The research program includes 17+ published papers on the Field-Node-Cockpit (FNC) framework, epistemic uncertainty in AI systems, and the philosophical and regulatory implications of autonomous AI.

ORCID: [0009-0000-4015-2357](https://orcid.org/0009-0000-4015-2357)
GitHub: [base76-research-lab](https://github.com/base76-research-lab)
Research: [Applied AI Philosophy](https://github.com/Applied-Ai-Philosophy)

---

*TrustPlane is built on [cognos-proof-engine](https://github.com/base76-research-lab/cognos-proof-engine) (MIT). The scoring engine is open source and independently auditable.*

*© 2026 Base76 Research Lab. Contact bjorn@base76.se for licensing.*

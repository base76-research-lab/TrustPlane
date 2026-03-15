# TrustPlane — Data Processing Agreement & NDA

**Annex A to Pilot Agreement / Standalone use**

**Base76 Research Lab · Björn Wikström · Sjöbo, Sweden**
**Contact:** bjorn@base76research.com

---

## Part 1 — Data Processing Agreement (DPA)

### 1.1 Roles

- **Data Controller:** Client (the organisation signing the Pilot Agreement)
- **Data Processor:** Base76 Research Lab (Provider)

This DPA governs all personal data processed by Provider on behalf of Controller through the TrustPlane platform, in accordance with GDPR (Regulation 2016/679).

### 1.2 Subject matter and purpose

Provider processes data submitted by Controller via the TrustPlane API solely to:
- Compute epistemic trust scores per request
- Store immutable audit traces (trace ID, timestamp, decision, trust score)
- Generate compliance reports on Controller's request

Provider does **not** use Controller data for training, analytics, or any purpose outside the above.

### 1.3 Categories of data

Controller determines what data is submitted. Provider processes metadata (request structure, timestamps, model outputs) and any content included in API calls. Controller is responsible for ensuring no unlawful data categories are submitted.

### 1.4 Retention

Audit traces are retained for 30 days during Pilot + 14-day grace period. On contract termination, all Controller data is deleted within 30 days unless Controller requests export first.

For paid SaaS tiers: default retention is 6 months (EU AI Act Art. 12 minimum). Configurable up to 7 years for regulated sectors.

### 1.5 Sub-processors

Provider may use the following sub-processors:

| Sub-processor | Purpose | Location |
|---|---|---|
| Anthropic / OpenAI / Groq / Cerebras | LLM inference (if selected by Controller) | US (SCCs apply) |
| PostgreSQL host (self-managed) | Audit log storage | EU |
| Redis host (self-managed) | Rate limiting | EU |

Controller will be notified of any changes to sub-processors with 14 days notice.

### 1.6 Security measures

Provider implements:
- API key authentication per tenant
- Schema-per-tenant PostgreSQL isolation (no cross-tenant data access)
- HTTPS in transit
- Docker container isolation
- Access logs retained

### 1.7 Data subject rights

Provider will assist Controller in responding to data subject requests (access, erasure, portability) within 5 business days of receiving a written request.

### 1.8 Breach notification

Provider will notify Controller within 72 hours of becoming aware of a personal data breach affecting Controller's data.

### 1.9 Governing law

This DPA is governed by Swedish law. Disputes are resolved in Swedish courts. Where GDPR applies, EU standard contractual clauses (2021/914) are incorporated by reference for international transfers.

---

## Part 2 — Non-Disclosure Agreement (NDA)

### 2.1 Definition of confidential information

"Confidential Information" means any non-public technical, commercial, or operational information disclosed by either party in connection with the Pilot, including but not limited to: source code, architecture, customer lists, pricing structures, and business strategy.

### 2.2 Obligations

Each party agrees to:
- Hold the other's Confidential Information in strict confidence
- Not disclose to third parties without prior written consent
- Use only for the purpose of evaluating or performing under this agreement
- Apply at minimum the same protection as for its own confidential information

### 2.3 Exceptions

Obligations do not apply to information that:
- Is or becomes publicly available without breach of this agreement
- Was already known to the receiving party at time of disclosure
- Is independently developed without use of Confidential Information
- Is required to be disclosed by law or regulatory authority (with prior notice where permitted)

### 2.4 Term

Confidentiality obligations survive termination of the Pilot Agreement for **24 months**.

### 2.5 Remedies

Each party acknowledges that breach may cause irreparable harm for which monetary damages are insufficient, and that injunctive relief may be sought without bond.

---

## Signatures

**Provider**
Björn Wikström, Base76 Research Lab
Date: _______________
Signature: _______________

**Client**
Name: _______________
Title: _______________
Organisation: _______________
Date: _______________
Signature: _______________

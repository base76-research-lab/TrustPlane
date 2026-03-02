# Scenario: Healthcare AI with Automatic Escalation

## Context

A hospital system deploys an AI assistant for clinical documentation. Physicians dictate notes; the AI structures them into EHR-compatible records. The system processes ~2,000 requests per day across three departments.

**Regulatory context:** EU AI Act Annex III (high-risk), GDPR Article 9 (health data), MDR (if used in clinical decision support).

**Failure mode without TrustPlane:** A model hallucinating a drug dosage or contraindication reaches the EHR. There is no record of what the model was asked, what it answered, or whether anyone reviewed it.

---

## Deployment

```
┌────────────────────────────────────────────────────────┐
│                   Hospital Network (air-gapped)         │
│                                                        │
│  ┌──────────────┐         ┌────────────────────────┐   │
│  │  Clinical    │  POST   │      TrustPlane         │   │
│  │  Documenta-  │────────▶│                        │   │
│  │  tion App    │         │  target_risk: 0.05     │   │
│  └──────────────┘         │  (5% threshold —       │   │
│                           │   strict for clinical) │   │
│                           └────────────┬───────────┘   │
│                                        │               │
│              ┌─────────────────────────┤               │
│              │                         │               │
│        PASS (0.95+)           ESCALATE/BLOCK           │
│              │                         │               │
│              ▼                         ▼               │
│  ┌──────────────────┐     ┌────────────────────────┐   │
│  │  EHR System      │     │  Clinical Review Queue │   │
│  │  (auto-populated)│     │  (physician reviews    │   │
│  └──────────────────┘     │   before EHR entry)    │   │
│                           └────────────────────────┘   │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Ollama + llama3.2 (local, no data leaves site)  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## Configuration

```yaml
# enterprise/config/hospital-system/provider.yaml
provider: ollama
model: llama3.2:1b
target_risk: 0.05          # Strict — escalate if confidence < 95%
rate_limit: 5000/day
webhook_url: https://ehr.hospital.internal/cognos-events
audit_enabled: true
audit_retention_days: 3650  # 10 years (clinical record requirement)
```

---

## Request flow

**Normal documentation (PASS):**
```
Physician: "Patient, 67M, presented with chest pain. Troponin 0.04.
            ECG: ST elevation leads II, III, aVF. Diagnosis: STEMI."

TrustPlane scores: C = 0.97
Decision: PASS
→ EHR populated automatically
→ Trace saved: tr_4f91a2c3
```

**Ambiguous request (ESCALATE):**
```
Physician: "Patient may have had a reaction. Adjust medication accordingly."

TrustPlane scores: C = 0.31
  Ue high: "reaction" is ambiguous — unknown medication, unknown reaction type
  Ua high: insufficient context for clinical inference
Decision: ESCALATE
→ Webhook fires to Clinical Review Queue
→ Physician receives notification: "Documentation requires review before EHR entry"
→ Trace saved: tr_9b22f441
→ EHR entry blocked until manual approval
```

---

## Audit export

```bash
# Monthly EU AI Act Article 13 report
curl -H "X-API-Key: clinical-admin-key" \
  "https://trustplane.hospital.internal/v1/audit/export?format=pdf&from=2026-03-01" \
  -o march_compliance_report.pdf
```

Report contains: all trace IDs, decisions, trust scores, escalation count, blocked requests, model used, policy applied.

---

## What this solves

| Risk | Without TrustPlane | With TrustPlane |
|---|---|---|
| Hallucinated dosage in EHR | Silent failure | ESCALATE → physician review |
| Ambiguous clinical note | Auto-populated | Blocked until reviewed |
| Regulatory audit | No documentation | Full trace log, PDF export |
| Data leaving hospital network | Depends on provider | Air-gapped Ollama, no external calls |
| Article 14 (human oversight) | Not implemented | Webhook escalation |

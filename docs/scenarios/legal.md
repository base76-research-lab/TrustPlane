# Scenario: Legal AI with Compliance Audit Trail

## Context

A law firm deploys AI for contract analysis and first-draft generation. Associates submit contracts for risk flagging; the AI identifies clauses, suggests redlines, and drafts summaries. The firm handles ~500 AI-assisted documents per month.

**Failure mode without TrustPlane:** An AI hallucinating a case citation or miscategorizing a liability clause is not caught until a partner review — or worse, not at all.

---

## Deployment

```
┌──────────────────────────────────────────────────────────┐
│                     Law Firm (SaaS)                       │
│                                                          │
│  ┌──────────────┐   POST    ┌──────────────────────────┐  │
│  │  Contract    │──────────▶│       TrustPlane          │  │
│  │  Analysis    │           │                          │  │
│  │  Platform    │           │  target_risk: 0.15       │  │
│  └──────────────┘           │  provider: anthropic     │  │
│                             │  model: claude-sonnet-   │  │
│                             │         4-6              │  │
│                             └────────────┬─────────────┘  │
│                                          │               │
│               ┌──────────────────────────┤               │
│               │                          │               │
│    PASS (trust ≥ 0.85)        ESCALATE / REFINE          │
│               │                          │               │
│               ▼                          ▼               │
│  ┌────────────────────┐    ┌─────────────────────────┐   │
│  │  Contract summary  │    │  Associate review queue │   │
│  │  delivered to      │    │  "AI confidence below   │   │
│  │  associate         │    │   threshold — verify    │   │
│  └────────────────────┘    │   before delivering"    │   │
│                            └─────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## Configuration

```yaml
provider: anthropic
model: claude-sonnet-4-6
api_key: ${ANTHROPIC_API_KEY}
target_risk: 0.15
rate_limit: 2000/month
webhook_url: https://matter-management.firm.com/ai-review
audit_enabled: true
audit_retention_days: 2555   # 7 years (legal retention requirement)
```

---

## Request flow

**Standard contract clause (PASS):**
```
Input: NDA with standard confidentiality clause, 2-year term, mutual obligations

TrustPlane scores: C = 0.91
Decision: PASS
→ Summary delivered: "Standard mutual NDA. Confidentiality period: 24 months.
   No unusual carve-outs identified."
→ Trace: tr_legal_8c3f
```

**Complex jurisdiction clause (REFINE):**
```
Input: M&A agreement with choice-of-law clause referencing
       2019 Delaware amendment and three cross-referenced exhibits

TrustPlane scores: C = 0.72
  Ue elevated: cross-jurisdictional references not fully resolved
Decision: REFINE
→ Summary delivered with warning header
→ X-TrustPlane-Decision: REFINE
→ Associate notified: "AI summary flagged for review — complex jurisdiction"
→ Trace: tr_legal_2a91
```

**Novel clause (ESCALATE):**
```
Input: AI-generated smart contract clause with
       self-executing liquidated damages in cryptocurrency

TrustPlane scores: C = 0.28
  Ue very high: novel legal instrument, limited precedent
Decision: ESCALATE
→ Webhook fires to partner review queue
→ No AI summary delivered until partner approves
→ Trace: tr_legal_f44c
```

---

## Audit value

Every AI-assisted document has a trace ID. If a client challenges an AI-generated deliverable:

```bash
curl -H "X-API-Key: admin-key" \
  "https://trustplane.firm.com/v1/traces/tr_legal_f44c"

# Returns:
# {
#   "trace_id": "tr_legal_f44c",
#   "decision": "ESCALATE",
#   "trust_score": 0.28,
#   "policy": "legal_v1",
#   "model": "claude-sonnet-4-6",
#   "created_at": "2026-03-02T09:14:22Z"
# }
```

The firm can demonstrate: what the model was asked, what decision was made, and that human review was triggered.

---

## What this solves

| Risk | Without TrustPlane | With TrustPlane |
|---|---|---|
| Hallucinated case citation | Caught (maybe) at partner review | ESCALATE before delivery |
| Complex clause misread | Silent | REFINE flag + associate notification |
| Novel instrument | AI guesses | ESCALATE → partner queue |
| Client challenges AI output | No documentation | Full trace with decision log |
| Professional liability | Undocumented AI use | Auditable per-document |

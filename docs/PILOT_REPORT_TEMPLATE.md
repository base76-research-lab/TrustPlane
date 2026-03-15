# TrustPlane Pilot Report
## [CLIENT NAME] · [DATE] · Confidential

**Prepared by:** Base76 Research Lab · bjorn@base76research.com
**Pilot period:** [START DATE] – [END DATE] (30 days)
**Tenant ID:** [TENANT_ID]

---

## Page 1 — Executive Summary

### What was measured

TrustPlane intercepted and scored every LLM inference in [CLIENT]'s [SYSTEM NAME] during the pilot period. Each request was evaluated against the epistemic trust formula:

```
C = p × (1 − Ue − Ua)
```

where `p` is prior confidence for the request type, `Ue` is epistemic uncertainty, and `Ua` is aleatoric uncertainty.

### Key findings

| Metric | Value |
|---|---|
| Total requests scored | [N] |
| PASS | [N] ([%]) |
| REFINE (warning) | [N] ([%]) |
| ESCALATE (human review triggered) | [N] ([%]) |
| BLOCK (rejected) | [N] ([%]) |
| Mean trust score | [0.XX] |
| Lowest recorded score | [0.XX] |
| Escalation webhooks fired | [N] |

### Headline assessment

> [1–2 sentences. Example: "27% of requests scored below the REFINE threshold, indicating material epistemic uncertainty in the contract analysis workflow. 4 requests were blocked for exceeding the minimum trust floor."]

### Recommendation

☐ Proceed to TrustPlane SaaS (EUR 999/month) — risk profile manageable with continuous monitoring
☐ Deep Audit recommended — evidence gaps require structured Article 11/13/14 mapping before deployment
☐ Policy recalibration — adjust `target_risk` and threshold config before production scale

---

## Page 2 — EU AI Act Compliance Map

### Applicability

[CLIENT]'s [SYSTEM NAME] processes [DESCRIBE USE CASE, e.g. "legal documents for contract review"]. Based on EU AI Act Annex III, this system [IS / MAY BE] classified as high-risk under category [X].

### Article coverage observed during pilot

| Article | Requirement | TrustPlane coverage | Gap |
|---|---|---|---|
| Art. 9 | Risk management system | ✓ Continuous epistemic scoring per request | [Note any gaps] |
| Art. 12 | Record-keeping | ✓ Immutable trace log, trace ID + timestamp per request | [Note retention config] |
| Art. 13 | Transparency | ✓ X-TrustPlane headers on every response | [Note if downstream logging needed] |
| Art. 14 | Human oversight | ✓ Webhook escalation on ESCALATE/BLOCK | [Note if incident process connected] |
| Art. 11 | Technical documentation | ✗ Not covered by TrustPlane alone | Deep Audit required |
| Art. 15 | Accuracy & robustness | Partial — scoring reflects uncertainty, not accuracy validation | [Note] |

### Observed compliance events

[List specific events from the pilot. Example:]
- `2026-03-08 14:22 CET` — Request tr_a3f91c2d44b1 scored 0.31 (ESCALATE). Content: contract clause extraction. Webhook fired to [ENDPOINT].
- `2026-03-12 09:44 CET` — 3 consecutive BLOCK events on high-uncertainty domain. Possible training distribution mismatch.

---

## Page 3 — Event Analysis

### Trust score distribution

```
Score range    Count    % of total
0.80 – 1.00    [N]      [%]         ████████████████
0.60 – 0.79    [N]      [%]         ████████
0.40 – 0.59    [N]      [%]         ████
0.20 – 0.39    [N]      [%]         ██
0.00 – 0.19    [N]      [%]         █
```

### Top escalation triggers

| Trigger pattern | Count | Risk signal |
|---|---|---|
| [E.g. "Multi-hop legal reasoning"] | [N] | High Ue — model uncertain |
| [E.g. "Regulatory citation requests"] | [N] | High Ua — domain noise |
| [E.g. "Conflicting document context"] | [N] | Low prior confidence |

### Hourly/daily pattern

[Describe if there are time-of-day patterns in low-trust requests. Example: "63% of ESCALATE events occurred between 08:00–10:00 CET, correlating with batch document processing. Recommend rate-limiting or dedicated policy for batch jobs."]

### Anomalies

[Note anything unexpected. Example: "One tenant sent 400 requests in 2 minutes on 2026-03-10. Rate limiter engaged correctly. No data exfiltration risk observed."]

---

## Page 4 — Next Steps & Recommendation

### What the data shows

[2–3 sentences synthesising the pilot findings for a non-technical reader — e.g. legal/compliance officer or board.]

Example: *"One in four AI decisions in your contract workflow carries measurable uncertainty that your current system does not flag. TrustPlane identified 12 cases where human review would have been warranted before the response reached your users. Continuous monitoring at this level costs EUR 999/month — less than one legal review hour per escalation event."*

### Options

**Option A — TrustPlane SaaS (recommended)**
EUR 999/month. This report delivered automatically every month. Policy tunable as your use cases evolve.
→ Sign order form, tenant stays live, billing starts [DATE + 7 days].

**Option B — Deep Audit**
EUR 20,000–80,000. Full provider-facing EU AI Act Article 11/13/14/15 mapping. Required if procurement, legal sign-off, or Annex III notification is pending.
→ Contact bjorn@base76research.com to scope.

**Option C — Self-hosted license**
EUR 25,000/year. Full source, air-gap compatible, no data leaves your environment.
→ Suitable if data sovereignty or procurement policy prevents SaaS.

### Immediate actions for [CLIENT]

1. [ ] Connect incident management webhook to TrustPlane ESCALATE events
2. [ ] Review [N] BLOCK events from pilot — confirm correct policy threshold
3. [ ] Confirm EU AI Act Annex III classification with legal/compliance team
4. [ ] Decision on continuation: _______________________________________________

---

*This report is confidential. Prepared by Base76 Research Lab under Pilot Agreement dated [DATE].*
*Trace log export available on request (CSV or PDF). Retention: 30 days post-pilot.*
*Contact: bjorn@base76research.com · base76research.com*

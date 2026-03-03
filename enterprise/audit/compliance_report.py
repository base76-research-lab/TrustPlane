from __future__ import annotations

import io
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RiskArea:
    name: str
    severity: str  # "low" | "medium" | "high"
    affected_traces: list[str]
    article_refs: list[str]
    explanation: str
    recommendation: str


@dataclass
class ComplianceReport:
    report_id: str
    tenant_id: str
    period_from: str
    period_to: str
    generated_at: str
    overall_risk_level: str  # "LOW" | "MEDIUM" | "HIGH"
    total_traces: int
    risk_areas: list[RiskArea]
    eu_ai_act_map: dict[str, str]
    raw_stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Risk area thresholds
# ---------------------------------------------------------------------------

_THRESHOLDS = {
    "epistemic_uncertainty": {
        "signal": "ue",
        "threshold": 0.3,
        "compare": "gt",
        "name": "Epistemic Uncertainty",
        "article_refs": ["Art. 9", "Art. 13"],
        "explanation_template": (
            "Epistemic uncertainty averaged {value:.1%} over the period, exceeding the "
            "recommended threshold of 30%. This indicates the model is operating outside "
            "its reliable knowledge domain on a significant portion of requests."
        ),
        "recommendation": (
            "Review the input distribution for this period. Consider retraining or fine-tuning "
            "the model on the affected domain, or add human-in-the-loop review for high-UE requests."
        ),
    },
    "model_divergence": {
        "signal": "divergence",
        "threshold": 0.2,
        "compare": "gt",
        "name": "Model Divergence",
        "article_refs": ["Art. 9", "Art. 14"],
        "explanation_template": (
            "Average divergence between the primary model and shadow models was {value:.1%}, "
            "surpassing the 20% threshold. Significant divergence implies the model's outputs "
            "are not consistent with ensemble expectations."
        ),
        "recommendation": (
            "Investigate shadow model disagreements for the flagged traces. "
            "Consider ensemble voting or escalation rules for high-divergence requests."
        ),
    },
    "high_escalation_rate": {
        "signal": "_escalation_rate",
        "threshold": 0.15,
        "compare": "gt",
        "name": "High Escalation Rate",
        "article_refs": ["Art. 14"],
        "explanation_template": (
            "The combined ESCALATE+BLOCK rate was {value:.1%}, above the 15% threshold. "
            "A high escalation rate may signal systematic policy over-triggering or "
            "an unusual input distribution requiring human oversight."
        ),
        "recommendation": (
            "Audit the escalation policy thresholds. Review blocked and escalated traces "
            "to determine whether the policy requires calibration or if genuine risk is present."
        ),
    },
    "aleatoric_uncertainty": {
        "signal": "ua",
        "threshold": 0.3,
        "compare": "gt",
        "name": "Aleatoric Uncertainty",
        "article_refs": ["Art. 13"],
        "explanation_template": (
            "Aleatoric (irreducible) uncertainty averaged {value:.1%}, exceeding 30%. "
            "This reflects inherent noise or ambiguity in the input data that cannot be "
            "resolved by model improvement alone."
        ),
        "recommendation": (
            "Communicate uncertainty levels to downstream consumers in API responses. "
            "Consider data quality improvements or uncertainty-aware output formatting."
        ),
    },
    "out_of_distribution": {
        "signal": "out_of_distribution",
        "threshold": 0.2,
        "compare": "gt",
        "name": "Out-of-Distribution Detection",
        "article_refs": ["Art. 9"],
        "explanation_template": (
            "Out-of-distribution (OOD) scores averaged {value:.1%}, above the 20% threshold. "
            "OOD inputs are outside the training distribution and increase the risk of "
            "unreliable or hallucinated outputs."
        ),
        "recommendation": (
            "Implement OOD filtering or rejection at the gateway level. "
            "Add explicit OOD warnings in API responses and log affected traces for review."
        ),
    },
    "citation_quality": {
        "signal": "citation_density",
        "threshold": 0.1,
        "compare": "lt",
        "name": "Citation Quality",
        "article_refs": ["Art. 12", "Art. 13"],
        "explanation_template": (
            "Average citation density was {value:.1%}, below the minimum recommended value of 10%. "
            "Low citation density reduces the verifiability and transparency of model outputs, "
            "which is a requirement under EU AI Act transparency provisions."
        ),
        "recommendation": (
            "Enable citation enforcement in the model prompt or post-processing pipeline. "
            "Require source references for factual claims and log citation metrics per trace."
        ),
    },
}


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------

def _extract_signals(trace: dict) -> dict[str, float]:
    """Extract signal values from a trace record."""
    # Signals may be in envelope.cognos.signals or top-level
    envelope = trace.get("envelope") or {}
    if isinstance(envelope, str):
        try:
            envelope = json.loads(envelope)
        except Exception:
            envelope = {}

    cognos = envelope.get("cognos") or {}
    signals = cognos.get("signals") or {}

    result: dict[str, float] = {}
    for key in ("ue", "ua", "divergence", "citation_density", "contradiction", "out_of_distribution"):
        for src in (signals, trace):
            val = src.get(key)
            if val is not None:
                try:
                    result[key] = float(val)
                    break
                except (TypeError, ValueError):
                    pass
    return result


def _compute_averages(traces: list[dict]) -> dict[str, float]:
    """Compute per-signal averages across all traces."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    escalation_count = 0

    for t in traces:
        sigs = _extract_signals(t)
        for k, v in sigs.items():
            sums[k] = sums.get(k, 0.0) + v
            counts[k] = counts.get(k, 0) + 1
        decision = str(t.get("decision", "")).upper()
        if decision in ("ESCALATE", "BLOCK"):
            escalation_count += 1

    avgs: dict[str, float] = {}
    for k in sums:
        avgs[k] = sums[k] / counts[k] if counts[k] else 0.0

    total = len(traces)
    avgs["_escalation_rate"] = escalation_count / total if total else 0.0
    return avgs


def _traces_exceeding(traces: list[dict], signal: str, threshold: float, compare: str) -> list[str]:
    """Return trace_ids where the signal crosses the threshold."""
    result = []
    for t in traces:
        if signal == "_escalation_rate":
            decision = str(t.get("decision", "")).upper()
            if decision in ("ESCALATE", "BLOCK"):
                result.append(t.get("trace_id", ""))
        else:
            sigs = _extract_signals(t)
            val = sigs.get(signal)
            if val is None:
                continue
            if compare == "gt" and val > threshold:
                result.append(t.get("trace_id", ""))
            elif compare == "lt" and val < threshold:
                result.append(t.get("trace_id", ""))
    return result


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def analyze_risk_areas(traces: list[dict]) -> list[RiskArea]:
    """
    Analyse traces by signal averages and return triggered risk areas.
    No LLM required — fully deterministic from trace signals.
    """
    if not traces:
        return []

    avgs = _compute_averages(traces)
    areas: list[RiskArea] = []

    for _key, cfg in _THRESHOLDS.items():
        signal = cfg["signal"]
        threshold = cfg["threshold"]
        compare = cfg["compare"]
        avg_val = avgs.get(signal, 0.0)

        triggered = (
            (compare == "gt" and avg_val > threshold) or
            (compare == "lt" and avg_val < threshold and avg_val > 0.0)
        )
        if not triggered:
            continue

        if compare == "gt":
            severity = "high" if avg_val > threshold * 1.5 else "medium"
        else:
            # citation_density: lower is worse
            severity = "high" if avg_val < threshold * 0.5 else "medium"

        affected = _traces_exceeding(traces, signal, threshold, compare)
        # Only mark low severity if very few traces affected
        if len(affected) < max(1, len(traces) * 0.05):
            severity = "low"

        explanation = cfg["explanation_template"].format(value=avg_val)

        areas.append(RiskArea(
            name=cfg["name"],
            severity=severity,
            affected_traces=affected,
            article_refs=cfg["article_refs"],
            explanation=explanation,
            recommendation=cfg["recommendation"],
        ))

    return areas


def _overall_risk(risk_areas: list[RiskArea]) -> str:
    if any(a.severity == "high" for a in risk_areas):
        return "HIGH"
    if any(a.severity == "medium" for a in risk_areas):
        return "MEDIUM"
    if risk_areas:
        return "LOW"
    return "LOW"


def _decision_breakdown(traces: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for t in traces:
        d = str(t.get("decision", "UNKNOWN")).upper()
        breakdown[d] = breakdown.get(d, 0) + 1
    return breakdown


def _eu_ai_act_map(risk_areas: list[RiskArea]) -> dict[str, str]:
    """Summarise compliance status per Article."""
    triggered_articles: set[str] = set()
    for area in risk_areas:
        for ref in area.article_refs:
            triggered_articles.add(ref)

    all_articles = ["Art. 9", "Art. 12", "Art. 13", "Art. 14"]
    return {
        art: "REVIEW_REQUIRED" if art in triggered_articles else "COMPLIANT"
        for art in all_articles
    }


def build_compliance_report(
    traces: list[dict],
    tenant_id: str,
    period_from: str,
    period_to: str,
) -> ComplianceReport:
    """Build a full ComplianceReport from a list of traces."""
    risk_areas = analyze_risk_areas(traces)
    overall = _overall_risk(risk_areas)
    breakdown = _decision_breakdown(traces)
    act_map = _eu_ai_act_map(risk_areas)

    avg_trust = (
        sum(float(t.get("trust_score", 0.0)) for t in traces) / len(traces)
        if traces else 0.0
    )

    return ComplianceReport(
        report_id=f"rpt_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        period_from=period_from,
        period_to=period_to,
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall_risk_level=overall,
        total_traces=len(traces),
        risk_areas=risk_areas,
        eu_ai_act_map=act_map,
        raw_stats={
            "decision_breakdown": breakdown,
            "avg_trust_score": round(avg_trust, 4),
            "total_traces": len(traces),
        },
    )


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

_SEVERITY_COLORS = {
    "high": (0.9, 0.2, 0.2),
    "medium": (0.95, 0.65, 0.0),
    "low": (0.2, 0.65, 0.2),
}

_RISK_COLORS = {
    "HIGH": (0.9, 0.2, 0.2),
    "MEDIUM": (0.95, 0.65, 0.0),
    "LOW": (0.2, 0.65, 0.2),
}


def render_pdf(report: ComplianceReport, tenant_id: str) -> bytes:
    """Generate a compliance PDF report using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # --- Cover page ---
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph("TrustPlane", styles["Title"]))
        elements.append(Paragraph("EU AI Act Compliance Report", styles["Heading1"]))
        elements.append(Spacer(1, 6 * mm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        elements.append(Spacer(1, 4 * mm))

        meta = [
            ["Tenant", tenant_id],
            ["Period", f"{report.period_from} — {report.period_to}"],
            ["Generated", report.generated_at[:19] + " UTC"],
            ["Report ID", report.report_id],
            ["Total Traces", str(report.total_traces)],
        ]
        meta_table = Table(meta, colWidths=[50 * mm, 110 * mm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 8 * mm))

        # Overall risk level badge
        risk_color = colors.Color(*_RISK_COLORS.get(report.overall_risk_level, (0.5, 0.5, 0.5)))
        risk_style = ParagraphStyle(
            "RiskBadge",
            parent=styles["Heading2"],
            textColor=risk_color,
        )
        elements.append(Paragraph(
            f"Overall Risk Level: {report.overall_risk_level}",
            risk_style,
        ))
        elements.append(Spacer(1, 6 * mm))

        # --- EU AI Act Article Status ---
        elements.append(Paragraph("EU AI Act — Article Compliance Status", styles["Heading2"]))
        elements.append(Spacer(1, 3 * mm))

        act_headers = [["Article", "Status", "Description"]]
        act_desc = {
            "Art. 9": "Risk management system",
            "Art. 12": "Record-keeping",
            "Art. 13": "Transparency and information to users",
            "Art. 14": "Human oversight",
        }
        act_rows = []
        for art, status in report.eu_ai_act_map.items():
            color_str = "red" if status == "REVIEW_REQUIRED" else "green"
            act_rows.append([art, status, act_desc.get(art, "")])

        act_table = Table(act_headers + act_rows, colWidths=[25 * mm, 45 * mm, 90 * mm])
        act_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]
        for i, (art, status) in enumerate(report.eu_ai_act_map.items(), start=1):
            if status == "REVIEW_REQUIRED":
                act_style.append(("TEXTCOLOR", (1, i), (1, i), colors.red))
            else:
                act_style.append(("TEXTCOLOR", (1, i), (1, i), colors.Color(0.1, 0.6, 0.1)))
        act_table.setStyle(TableStyle(act_style))
        elements.append(act_table)
        elements.append(Spacer(1, 8 * mm))

        # --- Risk Areas ---
        if report.risk_areas:
            elements.append(Paragraph("Risk Areas", styles["Heading2"]))
            elements.append(Spacer(1, 3 * mm))

            for area in report.risk_areas:
                sev_color = colors.Color(*_SEVERITY_COLORS.get(area.severity, (0.5, 0.5, 0.5)))
                sev_style = ParagraphStyle(
                    f"Sev_{area.severity}",
                    parent=styles["Heading3"],
                    textColor=sev_color,
                )
                section = [
                    Paragraph(f"{area.name} — {area.severity.upper()}", sev_style),
                    Paragraph(
                        f"<b>Articles:</b> {', '.join(area.article_refs)} &nbsp; "
                        f"<b>Affected traces:</b> {len(area.affected_traces)}",
                        styles["Normal"],
                    ),
                    Spacer(1, 2 * mm),
                    Paragraph(f"<b>Explanation:</b> {area.explanation}", styles["Normal"]),
                    Spacer(1, 1 * mm),
                    Paragraph(f"<b>Recommendation:</b> {area.recommendation}", styles["Normal"]),
                    Spacer(1, 4 * mm),
                    HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey),
                    Spacer(1, 3 * mm),
                ]
                elements.append(KeepTogether(section))
        else:
            elements.append(Paragraph("Risk Areas", styles["Heading2"]))
            elements.append(Paragraph(
                "No risk areas were identified in the analysed period. All signals are within thresholds.",
                styles["Normal"],
            ))
            elements.append(Spacer(1, 6 * mm))

        # --- Raw stats ---
        elements.append(Paragraph("Raw Statistics — Decision Breakdown", styles["Heading2"]))
        elements.append(Spacer(1, 3 * mm))

        stats_data = [["Decision", "Count"]] + [
            [k, str(v)]
            for k, v in report.raw_stats.get("decision_breakdown", {}).items()
        ]
        stats_data.append(["Avg Trust Score", f"{report.raw_stats.get('avg_trust_score', 0):.4f}"])
        stats_table = Table(stats_data, colWidths=[60 * mm, 40 * mm])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 8 * mm))

        # --- Appendix: top 50 traces ---
        elements.append(Paragraph("Appendix — Trace Log (top 50)", styles["Heading2"]))
        elements.append(Spacer(1, 3 * mm))

        trace_headers = ["Trace ID", "Decision", "Trust", "Model", "Created"]
        trace_rows = [trace_headers] + [
            [
                str(t.get("trace_id", ""))[:16] + "…",
                str(t.get("decision", "")),
                f"{float(t.get('trust_score', 0)):.2f}",
                str(t.get("model", ""))[:20],
                str(t.get("created_at", ""))[:19],
            ]
            for t in report.raw_stats.get("_traces_sample", [])
        ]
        if len(trace_rows) > 1:
            trace_table = Table(trace_rows, colWidths=[40 * mm, 25 * mm, 15 * mm, 35 * mm, 45 * mm])
            trace_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            ]))
            elements.append(trace_table)
        else:
            elements.append(Paragraph("No trace data available.", styles["Normal"]))

        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        return _minimal_compliance_pdf(report)


def _minimal_compliance_pdf(report: ComplianceReport) -> bytes:
    """Fallback plain-text PDF stub when reportlab is unavailable."""
    lines = [
        "TrustPlane Compliance Report",
        f"Tenant: {report.tenant_id}",
        f"Period: {report.period_from} -- {report.period_to}",
        f"Risk Level: {report.overall_risk_level}",
        f"Traces: {report.total_traces}",
        f"Generated: {report.generated_at}",
    ]
    for area in report.risk_areas:
        lines.append(f"\nRisk Area: {area.name} [{area.severity}]")
        lines.append(area.explanation)
        lines.append(f"Recommendation: {area.recommendation}")
    content = "\n".join(lines).encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"%%EOF\n"
    )

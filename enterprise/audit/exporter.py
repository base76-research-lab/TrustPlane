from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_csv(traces: list[dict[str, Any]]) -> str:
    """Export traces to CSV string."""
    if not traces:
        return ""

    fields = [
        "trace_id", "created_at", "decision", "policy",
        "trust_score", "risk", "model", "status_code", "is_stream",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in traces:
        writer.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue()


def export_pdf(traces: list[dict[str, Any]], tenant_id: str) -> bytes:
    """
    Generate EU AI Act Article 13 compliance report as PDF.
    Uses reportlab if available; falls back to plain-text PDF stub.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("CognOS Enterprise — Audit Report", styles["Title"]))
        elements.append(Paragraph(f"Tenant: {tenant_id}", styles["Normal"]))
        elements.append(Paragraph(f"Total traces: {len(traces)}", styles["Normal"]))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("EU AI Act — Article 13 Transparency Report", styles["Heading2"]))
        elements.append(Spacer(1, 6))

        if traces:
            headers = ["Trace ID", "Decision", "Trust Score", "Model", "Created"]
            data = [headers] + [
                [
                    t.get("trace_id", "")[:16] + "…",
                    t.get("decision", ""),
                    f"{t.get('trust_score', 0):.2f}",
                    t.get("model", ""),
                    str(t.get("created_at", ""))[:19],
                ]
                for t in traces[:100]
            ]
            table = Table(data)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]))
            elements.append(table)

        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        # Minimal PDF stub if reportlab not installed
        return _minimal_pdf(tenant_id, len(traces))


def _minimal_pdf(tenant_id: str, count: int) -> bytes:
    content = f"CognOS Enterprise Audit Report\nTenant: {tenant_id}\nTraces: {count}\n"
    encoded = content.encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"%%EOF\n"
    )

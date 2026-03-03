const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8788";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const apiKey =
    typeof window !== "undefined"
      ? localStorage.getItem("tp_api_key") ?? ""
      : "";
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(opts?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Trace {
  trace_id: string;
  created_at: string;
  decision: "PASS" | "REFINE" | "ESCALATE" | "BLOCK";
  policy: string;
  trust_score: number;
  risk: number;
  model: string;
  is_stream: boolean;
  status_code: number;
  overridden: boolean;
  override_by?: string;
  override_at?: string;
  override_reason?: string;
}

export interface RiskArea {
  name: string;
  severity: "low" | "medium" | "high";
  affected_traces: string[];
  article_refs: string[];
  explanation: string;
  recommendation: string;
}

export interface ComplianceReport {
  report_id: string;
  tenant_id: string;
  period_from: string;
  period_to: string;
  generated_at: string;
  overall_risk_level: "LOW" | "MEDIUM" | "HIGH";
  total_traces: number;
  risk_areas: RiskArea[];
  eu_ai_act_map: Record<string, string>;
  raw_stats: {
    decision_breakdown: Record<string, number>;
    avg_trust_score: number;
    total_traces: number;
    mandate_coverage: {
      with_mandate: number;
      without_mandate: number;
      coverage_rate: number;
    };
  };
}

export interface ReportSummary {
  report_id: string;
  created_at: string;
  period_from: string;
  period_to: string;
  risk_level: string;
}

export interface TierInfo {
  tier: string;
  limits: unknown;
  upgrade_url: string | null;
}

// ── API calls ──────────────────────────────────────────────────────────────

export const api = {
  health: () => req<{ status: string; tier: string }>("/healthz"),

  tier: () => req<TierInfo>("/v1/tier"),

  traces: (from?: string, to?: string) => {
    const params = new URLSearchParams();
    if (from) params.set("from_ts", from);
    if (to) params.set("to_ts", to);
    // No list endpoint — use audit export as JSON workaround via compliance report
    return req<ComplianceReport>("/v1/audit/compliance-report", {
      method: "POST",
      body: JSON.stringify({ from: from ?? "2000-01-01", to: to ?? "2099-12-31", format: "json" }),
    });
  },

  complianceReport: (from: string, to: string) =>
    req<ComplianceReport>("/v1/audit/compliance-report", {
      method: "POST",
      body: JSON.stringify({ from, to, format: "json" }),
    }),

  reports: () => req<ReportSummary[]>("/v1/reports/"),

  report: (id: string) => req<ComplianceReport>(`/v1/reports/${id}`),

  override: (traceId: string, reason: string) =>
    req<{ overridden: boolean; message: string }>(`/v1/traces/${traceId}/override`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  pdfUrl: (reportId: string) => {
    const apiKey =
      typeof window !== "undefined"
        ? localStorage.getItem("tp_api_key") ?? ""
        : "";
    return `${BASE}/v1/reports/${reportId}/pdf?key=${encodeURIComponent(apiKey)}`;
  },
};

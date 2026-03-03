"use client";
import { useEffect, useState } from "react";
import { api, ComplianceReport } from "@/lib/api";
import { fmtPercent } from "@/lib/utils";
import { RiskBadge, SeverityChip } from "@/components/RiskBadge";
import { ApiKeyGate } from "@/components/ApiKeyGate";
import { AlertTriangle, CheckCircle } from "lucide-react";

function MandateGauge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const color = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-zinc-400">Decision mandate coverage</span>
        <span className="font-semibold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-zinc-100">{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

  useEffect(() => {
    api.complianceReport(monthAgo, today)
      .then(setReport)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <ApiKeyGate>
      <div className="space-y-8 max-w-5xl">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Översikt</h1>
          <p className="text-sm text-zinc-500 mt-1">Senaste 30 dagarna · {monthAgo} — {today}</p>
        </div>

        {loading && <div className="text-zinc-500 text-sm animate-pulse">Hämtar rapport...</div>}
        {error && (
          <div className="bg-red-950/40 border border-red-800 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {report && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Risk Level</p>
                <RiskBadge level={report.overall_risk_level} />
              </div>
              <StatCard label="Totala traces" value={String(report.total_traces)} />
              <StatCard label="Avg trust score" value={report.raw_stats.avg_trust_score.toFixed(3)} />
              <StatCard
                label="Mandate coverage"
                value={fmtPercent(report.raw_stats.mandate_coverage?.coverage_rate ?? 0)}
                sub={`${report.raw_stats.mandate_coverage?.with_mandate ?? 0} av ${report.total_traces}`}
              />
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <MandateGauge rate={report.raw_stats.mandate_coverage?.coverage_rate ?? 0} />
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-zinc-300 mb-4">Besluts-breakdown</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(report.raw_stats.decision_breakdown).map(([d, n]) => (
                  <div key={d} className="bg-zinc-800 rounded-lg p-3 text-center">
                    <p className="text-lg font-bold text-zinc-100">{n}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">{d}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-zinc-300 mb-4">EU AI Act — Artikelstatus</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(report.eu_ai_act_map).map(([art, status]) => (
                  <div key={art} className="bg-zinc-800 rounded-lg p-3 flex items-center gap-2">
                    {status === "COMPLIANT"
                      ? <CheckCircle size={14} className="text-emerald-400 shrink-0" />
                      : <AlertTriangle size={14} className="text-amber-400 shrink-0" />}
                    <div>
                      <p className="text-xs font-semibold text-zinc-200">{art}</p>
                      <p className={`text-xs ${status === "COMPLIANT" ? "text-emerald-500" : "text-amber-500"}`}>
                        {status === "COMPLIANT" ? "Compliant" : "Review"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {report.risk_areas.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-zinc-300">Riskområden</h2>
                {report.risk_areas.map((area, i) => (
                  <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-2">
                    <div className="flex items-center gap-3">
                      <SeverityChip severity={area.severity} />
                      <span className="font-semibold text-zinc-100">{area.name}</span>
                      <span className="ml-auto text-xs text-zinc-500">{area.article_refs.join(", ")}</span>
                    </div>
                    <p className="text-sm text-zinc-400">{area.explanation}</p>
                    <p className="text-sm text-blue-400">→ {area.recommendation}</p>
                    <p className="text-xs text-zinc-600">{area.affected_traces.length} traces berörda</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </ApiKeyGate>
  );
}

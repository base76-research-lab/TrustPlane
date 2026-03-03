"use client";
import { useEffect, useState } from "react";
import { api, ReportSummary, ComplianceReport } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { ApiKeyGate } from "@/components/ApiKeyGate";
import { SeverityChip } from "@/components/RiskBadge";
import { Download, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

export default function ReportsPage() {
  const [summaries, setSummaries] = useState<ReportSummary[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, ComplianceReport>>({});
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

  const load = () => api.reports().then(setSummaries).catch(e => setError(e.message));

  useEffect(() => { load(); }, []);

  const generate = async () => {
    setGenerating(true);
    try {
      await api.complianceReport(monthAgo, today);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const expand = async (id: string) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (!detail[id]) {
      const r = await api.report(id);
      setDetail(d => ({ ...d, [id]: r }));
    }
  };

  return (
    <ApiKeyGate>
      <div className="space-y-6 max-w-4xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Compliance-rapporter</h1>
            <p className="text-sm text-zinc-500 mt-1">Sparade EU AI Act-rapporter per tenant</p>
          </div>
          <button
            onClick={generate}
            disabled={generating}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            <RefreshCw size={14} className={generating ? "animate-spin" : ""} />
            Generera ny
          </button>
        </div>

        {error && (
          <div className="bg-red-950/40 border border-red-800 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        {summaries.length === 0 && !error && (
          <div className="text-zinc-500 text-sm">Inga sparade rapporter ännu.</div>
        )}

        <div className="space-y-2">
          {summaries.map(s => (
            <div key={s.report_id} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <button
                onClick={() => expand(s.report_id)}
                className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-zinc-800/50 transition-colors"
              >
                <div className={`w-2 h-2 rounded-full shrink-0 ${
                  s.risk_level === "HIGH" ? "bg-red-500" :
                  s.risk_level === "MEDIUM" ? "bg-amber-500" : "bg-emerald-500"
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-zinc-100 truncate">{s.report_id}</p>
                  <p className="text-xs text-zinc-500">{fmtDate(s.created_at)}</p>
                </div>
                <span className={`text-xs font-semibold ${
                  s.risk_level === "HIGH" ? "text-red-400" :
                  s.risk_level === "MEDIUM" ? "text-amber-400" : "text-emerald-400"
                }`}>{s.risk_level}</span>
                <a
                  href={api.pdfUrl(s.report_id)}
                  target="_blank"
                  onClick={e => e.stopPropagation()}
                  className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
                >
                  <Download size={14} />
                </a>
                {expanded === s.report_id ? <ChevronUp size={14} className="text-zinc-500" /> : <ChevronDown size={14} className="text-zinc-500" />}
              </button>

              {expanded === s.report_id && detail[s.report_id] && (
                <div className="border-t border-zinc-800 px-5 py-4 space-y-4">
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div><p className="text-zinc-500 text-xs">Traces</p><p className="font-semibold">{detail[s.report_id].total_traces}</p></div>
                    <div><p className="text-zinc-500 text-xs">Avg trust</p><p className="font-semibold">{detail[s.report_id].raw_stats.avg_trust_score.toFixed(3)}</p></div>
                    <div><p className="text-zinc-500 text-xs">Mandate cov.</p><p className="font-semibold">{((detail[s.report_id].raw_stats.mandate_coverage?.coverage_rate ?? 0) * 100).toFixed(0)}%</p></div>
                  </div>
                  {detail[s.report_id].risk_areas.map((a, i) => (
                    <div key={i} className="bg-zinc-800 rounded-lg p-3 space-y-1">
                      <div className="flex items-center gap-2">
                        <SeverityChip severity={a.severity} />
                        <span className="text-sm font-medium text-zinc-200">{a.name}</span>
                        <span className="ml-auto text-xs text-zinc-500">{a.article_refs.join(", ")}</span>
                      </div>
                      <p className="text-xs text-zinc-400">{a.explanation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </ApiKeyGate>
  );
}

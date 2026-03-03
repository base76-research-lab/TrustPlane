"use client";
import { useEffect, useState, useRef } from "react";
import { api, ComplianceReport } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { DecisionChip } from "@/components/RiskBadge";
import { ApiKeyGate } from "@/components/ApiKeyGate";
import { RefreshCw, ShieldCheck } from "lucide-react";

interface TraceRow {
  trace_id: string;
  created_at: string;
  decision: string;
  trust_score: number;
  model: string;
  overridden: boolean;
  override_reason?: string;
}

function OverrideModal({ traceId, onDone, onClose }: { traceId: string; onDone: () => void; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (reason.trim().length < 5) { setErr("Ange minst 5 tecken."); return; }
    setLoading(true);
    try {
      await api.override(traceId, reason.trim());
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl p-6 w-full max-w-md space-y-4">
        <h3 className="font-semibold text-zinc-100">Signera override</h3>
        <p className="text-xs text-zinc-500 font-mono break-all">{traceId}</p>
        <textarea
          value={reason}
          onChange={e => setReason(e.target.value)}
          placeholder="Ange skäl för override (Art. 14 kräver dokumentation)..."
          rows={3}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {err && <p className="text-red-400 text-xs">{err}</p>}
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200">Avbryt</button>
          <button
            onClick={submit}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium"
          >
            <ShieldCheck size={14} />
            {loading ? "Sparar..." : "Signera"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [overrideTarget, setOverrideTarget] = useState<string | null>(null);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async () => {
    try {
      const report = await api.complianceReport("2000-01-01", "2099-12-31");
      // Extract trace sample from raw_stats if available
      const sample = (report.raw_stats as any)._traces_sample ?? [];
      if (sample.length > 0) {
        setTraces(sample);
      } else {
        // Build minimal rows from risk area affected_traces
        const ids = new Set(report.risk_areas.flatMap(a => a.affected_traces));
        setTraces([...ids].map(id => ({
          trace_id: id,
          created_at: new Date().toISOString(),
          decision: "ESCALATE",
          trust_score: 0,
          model: "—",
          overridden: false,
        })));
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 10000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const needsReview = (t: TraceRow) =>
    (t.decision === "ESCALATE" || t.decision === "BLOCK") && !t.overridden;

  return (
    <ApiKeyGate>
      {overrideTarget && (
        <OverrideModal
          traceId={overrideTarget}
          onDone={() => { setOverrideTarget(null); load(); }}
          onClose={() => setOverrideTarget(null)}
        />
      )}
      <div className="space-y-6 max-w-5xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Traces</h1>
            <p className="text-sm text-zinc-500 mt-1">Live · uppdateras var 10:e sekund</p>
          </div>
          <button onClick={load} className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 text-sm">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Uppdatera
          </button>
        </div>

        {error && (
          <div className="bg-red-950/40 border border-red-800 rounded-xl p-4 text-red-400 text-sm">{error}</div>
        )}

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-xs text-zinc-500 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Trace ID</th>
                <th className="text-left px-4 py-3">Beslut</th>
                <th className="text-left px-4 py-3">Trust</th>
                <th className="text-left px-4 py-3">Modell</th>
                <th className="text-left px-4 py-3">Tid</th>
                <th className="text-left px-4 py-3">Åtgärd</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {traces.length === 0 && !loading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-zinc-600 text-xs">Inga traces</td></tr>
              )}
              {traces.map(t => (
                <tr key={t.trace_id} className={`hover:bg-zinc-800/40 transition-colors ${needsReview(t) ? "bg-amber-950/10" : ""}`}>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-400 truncate max-w-[140px]">{t.trace_id}</td>
                  <td className="px-4 py-3"><DecisionChip decision={t.decision} /></td>
                  <td className="px-4 py-3 text-zinc-300">{t.trust_score ? t.trust_score.toFixed(3) : "—"}</td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{t.model}</td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{t.created_at ? fmtDate(t.created_at) : "—"}</td>
                  <td className="px-4 py-3">
                    {t.overridden ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-500">
                        <ShieldCheck size={12} /> Signerad
                      </span>
                    ) : needsReview(t) ? (
                      <button
                        onClick={() => setOverrideTarget(t.trace_id)}
                        className="text-xs bg-amber-900/30 hover:bg-amber-900/60 border border-amber-800 text-amber-400 rounded px-2 py-1 transition-colors"
                      >
                        Override
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </ApiKeyGate>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";

type TrustScore = { agent: string; avg: number; count: number };
type Cooldown = { expires_at: string; set_at: string; minutes: number };
type Event = {
  type?: string; agent?: string; topic?: string;
  trust?: number; risk?: number; decision?: string;
  reason?: string; action?: string; ts?: string;
};
type DashboardData = {
  ts: string; trust_scores: TrustScore[];
  cooldowns: Record<string, Cooldown>; bus: Record<string, number>;
  stop_hook_events: Event[]; heatmap: Record<string, Record<number, number>>;
  total_events: number; total_stop_hooks: number;
};

const trustColor = (v: number) => v >= 0.75 ? "text-emerald-400" : v >= 0.55 ? "text-yellow-400" : "text-red-400";
const trustBg = (v: number) => v >= 0.75 ? "bg-emerald-900/40 border-emerald-700" : v >= 0.55 ? "bg-yellow-900/40 border-yellow-700" : "bg-red-900/40 border-red-700";
const cooldownLeft = (exp: string) => { const d = new Date(exp).getTime() - Date.now(); return d <= 0 ? "utgången" : `${Math.ceil(d/60000)} min kvar`; };
const fmtDate = (iso?: string) => iso ? new Date(iso).toLocaleString("sv-SE", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" }) : "—";

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [refresh, setRefresh] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/dashboard");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setRefresh(new Date().toLocaleTimeString("sv-SE"));
      setErr("");
    } catch (e) { setErr(String(e)); }
  }, []);

  useEffect(() => { load(); const iv = setInterval(load, 30000); return () => clearInterval(iv); }, [load]);

  if (err) return <div className="min-h-screen bg-gray-950 text-red-400 flex items-center justify-center font-mono">API Error: {err}</div>;
  if (!data) return <div className="min-h-screen bg-gray-950 text-gray-500 flex items-center justify-center font-mono">Laddar...</div>;

  const cooldowns = Object.entries(data.cooldowns).filter(([,v]) => new Date(v.expires_at) > new Date());
  const heatAgents = Object.keys(data.heatmap);

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 font-mono p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight">CognOS Risk Dashboard</h1>
          <p className="text-gray-500 text-sm">Base76 Research Lab — epistemic trust monitor</p>
        </div>
        <div className="text-right text-xs text-gray-600">
          <div>{data.total_events} events · {data.total_stop_hooks} stop-hooks</div>
          <div className="text-gray-700">uppdaterad {refresh}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Trust per agent</h2>
          {data.trust_scores.length === 0 ? <p className="text-gray-600 text-sm">Ingen data ännu</p> : (
            <div className="space-y-2">
              {[...data.trust_scores].sort((a,b)=>b.avg-a.avg).map(t => (
                <div key={t.agent} className={`flex items-center justify-between px-3 py-2 rounded border ${trustBg(t.avg)}`}>
                  <span className="text-sm">{t.agent}</span>
                  <div><span className={`font-bold ${trustColor(t.avg)}`}>{t.avg.toFixed(2)}</span><span className="text-gray-600 text-xs ml-2">n={t.count}</span></div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Aktiva cooldowns</h2>
          {cooldowns.length === 0 ? <p className="text-gray-600 text-sm">Inga aktiva cooldowns</p> : (
            <div className="space-y-2">
              {cooldowns.map(([topic, cd]) => (
                <div key={topic} className="bg-orange-900/30 border border-orange-800 rounded px-3 py-2">
                  <div className="text-sm text-orange-300 truncate">{topic}</div>
                  <div className="text-xs text-orange-500">{cooldownLeft(cd.expires_at)} ({cd.minutes} min)</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Bus status</h2>
          {Object.keys(data.bus).length === 0 ? <p className="text-gray-600 text-sm">Bussen är tom</p> : (
            <div className="space-y-2">
              {Object.entries(data.bus).map(([s, c]) => (
                <div key={s} className="flex justify-between items-center px-3 py-2 bg-gray-800 rounded">
                  <span className="text-sm text-gray-400">{s}</span>
                  <span className={`font-bold text-sm ${s==="escalate_to_claude"?"text-red-400":s==="done"?"text-emerald-400":"text-yellow-400"}`}>{c}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {heatAgents.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
          <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Risk Heatmap — stop-hook triggers senaste 24h</h2>
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead><tr>
                <th className="text-left text-gray-600 pb-2 pr-4">Agent</th>
                {Array.from({length:24},(_,i) => <th key={i} className="text-gray-700 pb-2 px-1 text-center w-6">{i===0?"nu":`-${i}h`}</th>)}
              </tr></thead>
              <tbody>
                {heatAgents.map(agent => (
                  <tr key={agent}>
                    <td className="text-gray-400 pr-4 py-1">{agent}</td>
                    {Array.from({length:24},(_,h) => {
                      const n = data.heatmap[agent]?.[h]||0;
                      return <td key={h} className="px-1 py-1 text-center">
                        <div className={`w-5 h-5 rounded-sm mx-auto flex items-center justify-center text-xs ${n===0?"bg-gray-800":n===1?"bg-red-900 text-red-300":n<4?"bg-red-700 text-red-200":"bg-red-500 text-white"}`}>{n>0?n:""}</div>
                      </td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-xs text-gray-500 uppercase tracking-widest mb-3">Stop-hook historik</h2>
        {data.stop_hook_events.length === 0 ? <p className="text-gray-600 text-sm">Inga stop-hook events ännu</p> : (
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead><tr className="text-gray-600 border-b border-gray-800">
                {["Tid","Agent","Topic","Trust","Risk","Action","Orsak"].map(h=><th key={h} className="text-left pb-2 pr-4">{h}</th>)}
              </tr></thead>
              <tbody>
                {data.stop_hook_events.map((e,i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-1.5 pr-4 text-gray-500">{fmtDate(e.ts)}</td>
                    <td className="py-1.5 pr-4 text-gray-300">{e.agent||"—"}</td>
                    <td className="py-1.5 pr-4 text-gray-400 max-w-xs truncate">{e.topic||"—"}</td>
                    <td className={`py-1.5 pr-4 font-bold ${trustColor(e.trust??1)}`}>{typeof e.trust==="number"?e.trust.toFixed(2):"—"}</td>
                    <td className="py-1.5 pr-4 text-orange-400">{typeof e.risk==="number"?e.risk.toFixed(2):"—"}</td>
                    <td className="py-1.5 pr-4">
                      <span className={`px-2 py-0.5 rounded text-xs ${e.decision==="HARD_STOP"?"bg-red-900 text-red-300":e.decision==="ESCALATE"?"bg-orange-900 text-orange-300":"bg-yellow-900 text-yellow-300"}`}>
                        {e.decision||e.action||"—"}
                      </span>
                    </td>
                    <td className="py-1.5 text-gray-600 max-w-xs truncate">{e.reason||"—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

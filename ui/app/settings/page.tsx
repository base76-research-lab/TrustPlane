"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { ApiKeyGate } from "@/components/ApiKeyGate";
import { KeyRound, Server, LogOut } from "lucide-react";

export default function SettingsPage() {
  const [tier, setTier] = useState<any>(null);
  const [apiKey, setApiKey] = useState("");
  const [apiUrl, setApiUrl] = useState("");

  useEffect(() => {
    setApiKey(localStorage.getItem("tp_api_key") ?? "");
    setApiUrl(localStorage.getItem("tp_api_url") ?? "http://localhost:8788");
    api.tier().then(setTier).catch(() => {});
  }, []);

  const save = () => {
    localStorage.setItem("tp_api_key", apiKey);
    localStorage.setItem("tp_api_url", apiUrl);
    window.location.reload();
  };

  const logout = () => {
    localStorage.removeItem("tp_api_key");
    window.location.reload();
  };

  return (
    <ApiKeyGate>
      <div className="space-y-6 max-w-lg">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Inställningar</h1>
          <p className="text-sm text-zinc-500 mt-1">Anslutning och autentisering</p>
        </div>

        {tier && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex items-center gap-3">
            <Server size={16} className="text-blue-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-zinc-200">Tier: <span className="text-blue-400 capitalize">{tier.tier}</span></p>
              {tier.upgrade_url && (
                <a href={tier.upgrade_url} className="text-xs text-zinc-500 hover:text-zinc-300">Uppgradera →</a>
              )}
            </div>
          </div>
        )}

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-300">
            <KeyRound size={14} /> Anslutningsinställningar
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">API URL</label>
              <input
                value={apiUrl}
                onChange={e => setApiUrl(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 mb-1 block">API-nyckel</label>
              <input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-2 text-sm font-medium transition-colors">
              Spara
            </button>
            <button onClick={logout} className="flex items-center gap-1.5 px-4 py-2 text-sm text-red-400 hover:text-red-300 border border-zinc-800 rounded-lg transition-colors">
              <LogOut size={13} /> Logga ut
            </button>
          </div>
        </div>
      </div>
    </ApiKeyGate>
  );
}

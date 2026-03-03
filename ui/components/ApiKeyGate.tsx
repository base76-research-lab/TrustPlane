"use client";
import { useState, useEffect } from "react";
import { KeyRound } from "lucide-react";

export function ApiKeyGate({ children }: { children: React.ReactNode }) {
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [input, setInput] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem("tp_api_key");
    if (stored) { setKey(stored); setSaved(true); }
  }, []);

  if (saved && key) return <>{children}</>;

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full max-w-sm space-y-5">
        <div className="flex items-center gap-3">
          <KeyRound size={20} className="text-blue-400" />
          <h2 className="text-lg font-semibold">API-nyckel</h2>
        </div>
        <p className="text-sm text-zinc-400">
          Ange din TrustPlane API-nyckel för att fortsätta.
        </p>
        <input
          type="password"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && input) {
              localStorage.setItem("tp_api_key", input);
              setKey(input);
              setSaved(true);
            }
          }}
          placeholder="tp_..."
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={() => {
            if (!input) return;
            localStorage.setItem("tp_api_key", input);
            setKey(input);
            setSaved(true);
          }}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
        >
          Fortsätt
        </button>
      </div>
    </div>
  );
}

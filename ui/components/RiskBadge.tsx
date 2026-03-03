import { cn, SEVERITY_COLOR, RISK_COLOR } from "@/lib/utils";

export function RiskBadge({ level }: { level: string }) {
  return (
    <span className={cn("text-2xl font-bold", RISK_COLOR[level] ?? "text-zinc-400")}>
      {level}
    </span>
  );
}

export function SeverityChip({ severity }: { severity: string }) {
  return (
    <span className={cn(
      "text-xs font-medium px-2 py-0.5 rounded border uppercase tracking-wide",
      SEVERITY_COLOR[severity] ?? "bg-zinc-800 text-zinc-400 border-zinc-700"
    )}>
      {severity}
    </span>
  );
}

export function DecisionChip({ decision }: { decision: string }) {
  const colors: Record<string, string> = {
    PASS:     "bg-emerald-900/40 text-emerald-400 border-emerald-800",
    REFINE:   "bg-blue-900/40 text-blue-400 border-blue-800",
    ESCALATE: "bg-amber-900/40 text-amber-400 border-amber-800",
    BLOCK:    "bg-red-900/40 text-red-400 border-red-800",
  };
  return (
    <span className={cn(
      "text-xs font-mono font-semibold px-2 py-0.5 rounded border",
      colors[decision] ?? "bg-zinc-800 text-zinc-400 border-zinc-700"
    )}>
      {decision}
    </span>
  );
}

export function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("sv-SE", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export function fmtPercent(n: number) {
  return (n * 100).toFixed(1) + "%";
}

export const DECISION_COLOR: Record<string, string> = {
  PASS:     "bg-emerald-100 text-emerald-800",
  REFINE:   "bg-blue-100 text-blue-800",
  ESCALATE: "bg-amber-100 text-amber-800",
  BLOCK:    "bg-red-100 text-red-800",
};

export const SEVERITY_COLOR: Record<string, string> = {
  low:    "bg-emerald-100 text-emerald-700 border-emerald-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  high:   "bg-red-100 text-red-700 border-red-200",
};

export const RISK_COLOR: Record<string, string> = {
  LOW:    "text-emerald-600",
  MEDIUM: "text-amber-600",
  HIGH:   "text-red-600",
};

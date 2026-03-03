"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, FileText, Activity, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/",          label: "Översikt",      icon: ShieldCheck },
  { href: "/reports",   label: "Rapporter",     icon: FileText },
  { href: "/traces",    label: "Traces",        icon: Activity },
  { href: "/settings",  label: "Inställningar", icon: Settings },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 bg-zinc-900 border-r border-zinc-800 flex flex-col">
      <div className="px-6 py-5 border-b border-zinc-800">
        <span className="text-sm font-semibold tracking-widest text-zinc-400 uppercase">Trust</span>
        <span className="text-sm font-semibold tracking-widest text-blue-400 uppercase">Plane</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              path === href
                ? "bg-blue-600/20 text-blue-400 font-medium"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="px-6 py-4 border-t border-zinc-800 text-xs text-zinc-600">
        EU AI Act v1.2.0
      </div>
    </aside>
  );
}

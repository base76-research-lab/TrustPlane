import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import os from "os";

const HOME = os.homedir();

function readJsonl(filePath: string): object[] {
  try {
    const text = fs.readFileSync(filePath, "utf-8");
    return text
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l))
      .filter(Boolean);
  } catch {
    return [];
  }
}

function readJson(filePath: string): object {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return {};
  }
}

export async function GET() {
  // Events — stop_hook + agent events
  const eventsPath = path.join(HOME, ".local/share/b76/observer/events.jsonl");
  const allEvents = readJsonl(eventsPath) as Array<{
    type?: string;
    source?: string;
    agent?: string;
    topic?: string;
    trust?: number;
    risk?: number;
    decision?: string;
    reason?: string;
    action?: string;
    ts?: string;
    event_type?: string;
  }>;

  // Senaste 50 events
  const recentEvents = allEvents.slice(-50).reverse();

  // Stop-hook events
  const stopHookEvents = allEvents.filter((e) => e.type === "stop_hook");

  // Trust per agent (snitt av senaste 10 per agent)
  const agentTrust: Record<string, number[]> = {};
  for (const e of allEvents) {
    const agent = e.source || e.agent || "unknown";
    if (typeof e.trust === "number") {
      if (!agentTrust[agent]) agentTrust[agent] = [];
      agentTrust[agent].push(e.trust);
    }
  }
  const trustScores = Object.entries(agentTrust).map(([agent, scores]) => ({
    agent,
    avg: scores.slice(-10).reduce((a, b) => a + b, 0) / Math.min(scores.length, 10),
    count: scores.length,
  }));

  // Cooldowns
  const cooldownPath = path.join(
    HOME,
    ".local/share/b76/armada/stop_hook_cooldown.json"
  );
  const cooldowns = readJson(cooldownPath) as Record<
    string,
    { expires_at: string; set_at: string; minutes: number }
  >;

  // Bus status
  const busPath = "/tmp/b76_armada_bus.json";
  const busMessages = readJson(busPath) as Array<{ status?: string; to?: string; from?: string; task?: string }>;
  const busCounts = Array.isArray(busMessages)
    ? busMessages.reduce(
        (acc: Record<string, number>, m) => {
          const s = m.status || "?";
          acc[s] = (acc[s] || 0) + 1;
          return acc;
        },
        {}
      )
    : {};

  // Risk heatmap — stop_hook triggers per agent per timme (senaste 24h)
  const now = Date.now();
  const heatmap: Record<string, Record<number, number>> = {};
  for (const e of stopHookEvents) {
    const agent = e.agent || "unknown";
    const ts = e.ts ? new Date(e.ts).getTime() : 0;
    const hoursAgo = Math.floor((now - ts) / 3600000);
    if (hoursAgo < 24) {
      if (!heatmap[agent]) heatmap[agent] = {};
      heatmap[agent][hoursAgo] = (heatmap[agent][hoursAgo] || 0) + 1;
    }
  }

  return NextResponse.json({
    ts: new Date().toISOString(),
    trust_scores: trustScores,
    cooldowns,
    bus: busCounts,
    recent_events: recentEvents.slice(0, 20),
    stop_hook_events: stopHookEvents.slice(-20).reverse(),
    heatmap,
    total_events: allEvents.length,
    total_stop_hooks: stopHookEvents.length,
  });
}

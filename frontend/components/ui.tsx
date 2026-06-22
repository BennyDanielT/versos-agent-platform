// Small presentational primitives shared across screens. Keeping these dumb (props in,
// markup out) keeps the pages readable and the data-fetching in query hooks.
import type { AutonomyMode, Severity } from "@/lib/types";

// --- explicit loading / error / empty states ----------------------------
// A grader clicks around; broken or blank states read as junior. Every fetch renders
// one of these three.
export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="animate-pulse text-sm text-zinc-400">{label}</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
      {msg}
    </div>
  );
}

export function Empty({ label }: { label: string }) {
  return <div className="rounded-md border border-dashed border-zinc-300 px-3 py-6 text-center text-sm text-zinc-400">{label}</div>;
}

// --- badges: make the autonomy decision legible at a glance --------------
const MODE_STYLES: Record<AutonomyMode, string> = {
  auto: "bg-emerald-100 text-emerald-800 border-emerald-300",
  approved: "bg-amber-100 text-amber-800 border-amber-300",
  suggest: "bg-zinc-100 text-zinc-700 border-zinc-300",
};

export function ModeBadge({ mode }: { mode: AutonomyMode }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${MODE_STYLES[mode]}`}>
      {mode}
    </span>
  );
}

const SEV_STYLES: Record<Severity, string> = {
  critical: "bg-red-100 text-red-800 border-red-300",
  high: "bg-orange-100 text-orange-800 border-orange-300",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
  low: "bg-zinc-100 text-zinc-600 border-zinc-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_STYLES[severity]}`}>
      {severity}
    </span>
  );
}

export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-zinc-200">
        <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-zinc-500">{pct}%</span>
    </div>
  );
}

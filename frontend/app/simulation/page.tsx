"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, CardBody, CardHeader, ErrorBox, Stat } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { SimConfig } from "@/lib/types";

const DEFAULTS: SimConfig = {
  speed: 1,
  triage_enabled: true,
  triage_per_min: 6,
  pipeline_enabled: true,
  jobs_per_min: 30,
  job_fail_rate: 0.35,
  auto_heal: true,
  index_enabled: true,
  index_ops_per_min: 4,
  auto_scan: true,
};

export default function SimulationPage() {
  const qc = useQueryClient();
  // Poll status while the page is open so the stats tick live.
  const status = useQuery({
    queryKey: ["sim-status"],
    queryFn: () => api.simStatus(),
    refetchInterval: 2000,
  });

  // Local edits (null until the user touches a control). Until then we DISPLAY the server's
  // config directly — no effect syncing server→local state.
  const [edits, setEdits] = useState<SimConfig | null>(null);

  const running = status.data?.running ?? false;
  const stats = status.data?.stats;
  const cfg: SimConfig = edits ?? status.data?.config ?? DEFAULTS;

  const start = useMutation({
    mutationFn: () => api.simStart(cfg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sim-status"] }),
  });
  const stop = useMutation({
    mutationFn: () => api.simStop(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sim-status"] }),
  });
  const live = useMutation({ mutationFn: (p: Partial<SimConfig>) => api.simConfig(p) });

  // Set a knob; if the sim is running, push it live immediately.
  function set<K extends keyof SimConfig>(key: K, value: SimConfig[K]) {
    setEdits({ ...cfg, [key]: value });
    if (running) live.mutate({ [key]: value } as Partial<SimConfig>);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Simulation</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            A live, controllable feed. It doesn&apos;t insert fake rows — it creates the real
            upstream conditions each agent reacts to (jobs that fail, index problems, customer
            complaints), so every logged decision is produced by the real pipeline.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusDot running={running} />
          {running ? (
            <Button variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
              Stop
            </Button>
          ) : (
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? "Starting…" : "Start simulation"}
            </Button>
          )}
        </div>
      </header>

      {(start.isError || stop.isError) && <ErrorBox error={start.error ?? stop.error} />}

      {/* Live stats */}
      <section className="grid gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Uptime" value={stats ? `${Math.round(stats.uptime_sec)}s` : "—"} />
        <Stat label="Triage done" value={stats?.triage_done ?? "—"} hint={`${stats?.triage_errors ?? 0} errors`} />
        <Stat label="Jobs created" value={stats?.jobs_created ?? "—"} hint={`${stats?.jobs_processed ?? 0} processed`} />
        <Stat label="Jobs failed" value={stats?.jobs_failed ?? "—"} />
        <Stat label="Heals" value={stats?.heals ?? "—"} />
        <Stat label="Index ops" value={stats?.index_ops ?? "—"} />
        <Stat label="Scans" value={stats?.scans ?? "—"} />
        <Stat label="Errors" value={stats?.errors ?? "—"} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Global */}
        <Card>
          <CardHeader title="Global" subtitle="Speed multiplier applies to every rate" />
          <CardBody className="space-y-4">
            <Slider label="Speed" value={cfg.speed} min={0.25} max={10} step={0.25} suffix="×"
              onChange={(v) => set("speed", v)} />
          </CardBody>
        </Card>

        {/* Pipeline */}
        <Card>
          <CardHeader
            title="Pipeline Healer"
            subtitle="Jobs stream in, some fail, the healer sweeps them"
            action={<Toggle checked={cfg.pipeline_enabled} onChange={(v) => set("pipeline_enabled", v)} />}
          />
          <CardBody className="space-y-4">
            <Slider label="Jobs / min" value={cfg.jobs_per_min} min={0} max={240} step={5}
              onChange={(v) => set("jobs_per_min", v)} />
            <Slider label="Failure rate" value={cfg.job_fail_rate} min={0} max={1} step={0.05} suffix=""
              format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => set("job_fail_rate", v)} />
            <Toggle label="Auto-heal failures" checked={cfg.auto_heal} onChange={(v) => set("auto_heal", v)} />
          </CardBody>
        </Card>

        {/* Index */}
        <Card>
          <CardHeader
            title="Index Hygiene"
            subtitle="Real schema churn creates genuine findings"
            action={<Toggle checked={cfg.index_enabled} onChange={(v) => set("index_enabled", v)} />}
          />
          <CardBody className="space-y-4">
            <Slider label="Schema ops / min" value={cfg.index_ops_per_min} min={0} max={60} step={2}
              onChange={(v) => set("index_ops_per_min", v)} />
            <Toggle label="Auto-scan catalog" checked={cfg.auto_scan} onChange={(v) => set("auto_scan", v)} />
          </CardBody>
        </Card>

        {/* Triage */}
        <Card>
          <CardHeader
            title="Support Triage"
            subtitle="Real LLM calls — cost scales with rate"
            action={<Toggle checked={cfg.triage_enabled} onChange={(v) => set("triage_enabled", v)} />}
          />
          <CardBody className="space-y-4">
            <Slider label="Complaints / min" value={cfg.triage_per_min} min={0} max={60} step={1}
              onChange={(v) => set("triage_per_min", v)} />
            <p className="text-xs text-muted-foreground">
              Needs <code>NVIDIA_API_KEY</code>. Each complaint runs the real triage agent and
              writes a <code>triage_log</code> row. Turn off to demo Index + Pipeline at zero cost.
            </p>
          </CardBody>
        </Card>
      </div>

      <p className="text-xs text-muted-foreground">
        Changes apply live while running. Open the Dashboard or a vertical in another tab and watch
        it fill.
      </p>
    </div>
  );
}

function StatusDot({ running }: { running: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className={cn("h-2 w-2 rounded-full", running ? "animate-pulse bg-emerald-500" : "bg-zinc-400")} />
      {running ? "Running" : "Stopped"}
    </span>
  );
}

function Slider({
  label, value, min, max, step, suffix, format, onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  format?: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{format ? format(value) : `${value}${suffix ?? ""}`}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--primary)]"
      />
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-muted border border-border",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </button>
      {label && <span className="text-muted-foreground">{label}</span>}
    </label>
  );
}

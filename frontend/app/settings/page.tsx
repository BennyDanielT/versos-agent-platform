"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, ErrorBox, Loading } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { SystemFlag } from "@/lib/types";

// Human-friendly copy per flag. Anything not listed still renders generically.
const META: Record<string, { label: string; desc: string; danger?: boolean }> = {
  kill_switch: {
    label: "Kill switch",
    desc: "Force ALL agents to suggest-only — an instant, fleet-wide emergency stop for every autonomous action. Nothing acts without a human.",
    danger: true,
  },
  input_rail: {
    label: "NeMo input rail",
    desc: "LLM screening of off-topic / jailbreak input before triage runs (hard block). Costs an extra LLM call per ticket, so it's off by default.",
  },
  mask_input: {
    label: "Mask PII on input",
    desc: "Redact PII in the complaint before it reaches the model or the decision log (data minimization). Output masking is always on.",
  },
};

function Switch({ on, onClick, danger, disabled }: {
  on: boolean; onClick: () => void; danger?: boolean; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50",
        on ? (danger ? "bg-red-600" : "bg-primary") : "bg-muted",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
          on ? "translate-x-5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const flags = useQuery({ queryKey: ["flags"], queryFn: () => api.flags() });
  const setFlag = useMutation({
    mutationFn: (v: { name: string; enabled: boolean }) => api.setFlag(v.name, v.enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flags"] }),
  });

  const toggle = (f: SystemFlag) => setFlag.mutate({ name: f.name, enabled: !f.enabled });
  const kill = flags.data?.find((f) => f.name === "kill_switch");
  const others = flags.data?.filter((f) => f.name !== "kill_switch") ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Live runtime flags. These are <span className="font-medium text-foreground">DB-backed</span> and
          read per request, so a change takes effect <span className="font-medium text-foreground">instantly,
          fleet-wide, with no redeploy</span>.
        </p>
      </header>

      {flags.isLoading ? (
        <Loading />
      ) : flags.isError ? (
        <ErrorBox error={flags.error} />
      ) : (
        <>
          {/* Kill switch — the hero blast-radius control */}
          {kill && (
            <Card className={cn(kill.enabled ? "border-red-500/60 bg-red-500/10" : "border-red-500/25")}>
              <CardBody className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    {META.kill_switch.label}
                    {kill.enabled && (
                      <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-white">
                        Engaged
                      </span>
                    )}
                  </div>
                  <p className="mt-1 max-w-xl text-sm text-muted-foreground">{META.kill_switch.desc}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    updated by {kill.updated_by ?? "—"}
                  </p>
                </div>
                <Switch on={kill.enabled} danger onClick={() => toggle(kill)} disabled={setFlag.isPending} />
              </CardBody>
            </Card>
          )}

          {/* Guardrail toggles */}
          <Card>
            <CardHeader title="Guardrail toggles" subtitle="Screening + data-minimization" />
            <CardBody className="divide-y divide-border">
              {others.map((f) => {
                const m = META[f.name] ?? { label: f.name, desc: "" };
                return (
                  <div key={f.name} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                    <div>
                      <div className="text-sm font-medium">{m.label}</div>
                      <p className="mt-0.5 max-w-xl text-sm text-muted-foreground">{m.desc}</p>
                    </div>
                    <Switch on={f.enabled} onClick={() => toggle(f)} disabled={setFlag.isPending} />
                  </div>
                );
              })}
            </CardBody>
          </Card>

          {setFlag.isError && <ErrorBox error={setFlag.error} />}
        </>
      )}
    </div>
  );
}

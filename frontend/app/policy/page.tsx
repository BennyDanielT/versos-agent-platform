"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Empty, ErrorBox, Loading, ModeBadge } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { AutonomyMode, PolicyRow, SegmentMetric, Severity } from "@/lib/types";

const MODES: AutonomyMode[] = ["suggest", "approved", "auto"];
const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];
// The closed category taxonomy (must match TriageResult._CATEGORIES in the backend).
const CATEGORIES = ["billing", "media_quality", "account_access", "bug", "other"];

export default function PolicyPage() {
  const qc = useQueryClient();
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => api.policy() });
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: () => api.metrics() });

  const save = useMutation({
    mutationFn: (row: PolicyRow) => api.upsertPolicy({ ...row, updated_by: "console" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["policy"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <header>
          <h1 className="text-xl font-semibold">Autonomy policy</h1>
          <p className="text-sm text-zinc-500">
            The human-owned ceiling per segment. The agent can never exceed this — code enforces
            it. Edit a mode or confidence bar and save.
          </p>
        </header>

        {policy.isPending && <Loading label="Loading policy…" />}
        {policy.isError && <ErrorBox error={policy.error} />}
        {policy.data?.length === 0 && <Empty label="No policy rows configured." />}

        {policy.data && policy.data.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">Approved mode</th>
                  <th className="px-3 py-2">Min confidence</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {policy.data.map((row, i) => (
                  <PolicyRowEditor
                    key={`${row.severity}/${row.category}`}
                    row={row}
                    striped={i % 2 === 1}
                    onSave={(r) => save.mutate(r)}
                    saving={save.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        <AddSegmentForm
          existing={policy.data ?? []}
          onAdd={(r) => save.mutate(r)}
          saving={save.isPending}
        />
        {save.isError && <ErrorBox error={save.error} />}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Segment metrics</h2>
        <MetricsLegend />
        {metrics.isPending && <Loading label="Loading metrics…" />}
        {metrics.isError && <ErrorBox error={metrics.error} />}
        {metrics.data?.length === 0 && <Empty label="No metrics yet." />}
        {metrics.data && metrics.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {metrics.data.map((m, i) => (
              <MetricCard
                key={i}
                m={m}
                policyRow={policy.data?.find(
                  (p) => p.severity === m.severity && p.category === m.category,
                )}
                onPromote={(bar) =>
                  save.mutate({
                    severity: m.severity,
                    category: m.category,
                    approved_mode: "auto",
                    min_confidence: bar,
                  })
                }
                saving={save.isPending}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// Collapsible glossary: every metric, its formula, and why it matters. Lives here so it
// can be pointed at during a demo. Confidence bar = the segment's policy min_confidence.
function MetricsLegend() {
  const rows: { m: string; formula: string; why: string }[] = [
    { m: "total", formula: "count(tickets in segment)", why: "Volume — is there enough signal to trust any rate?" },
    { m: "reviewed", formula: "count(decision IS NOT NULL)", why: "Tickets a human judged — approve OR reject both count as reviewed." },
    { m: "approved", formula: "count(decision = 'approve')", why: "Of reviewed, how many the human agreed with." },
    { m: "accept_rate", formula: "approved / reviewed", why: "Online accuracy on reviewed tickets. Auto tickets are excluded (no decision)." },
    { m: "reviewed_eligible", formula: "reviewed tickets with confidence ≥ bar", why: "Size of the confident slice we'd actually let auto-act." },
    { m: "precision_eligible", formula: "approved / reviewed, within confidence ≥ bar", why: "Accuracy on the slice that would auto — THE gate for granting auto." },
    { m: "feedback", formula: "count(customer_satisfied IS NOT NULL)", why: "How many CSAT responses arrived (the auto-path signal volume)." },
    { m: "satisfaction_rate", formula: "👍 / feedback", why: "Auto-mode ground truth — auto tickets are never reviewed, so CSAT is their only accuracy signal." },
    { m: "eligible_for_auto", formula: "reviewed_eligible ≥ 3 AND accept_rate ≥ 0.66 AND precision_eligible ≥ 0.66", why: "Promotion readiness (demo thresholds; prod ≈ 20 / 0.95 / 0.97). Says whether the data justifies auto." },
    { m: "ECE (calibration)", formula: "Σ(n·|avg_confidence − accuracy|) / Σn, over 10 confidence bins", why: "Is the model's confidence honest? Lower = better calibrated. Tells you where to set the bar." },
  ];
  return (
    <details className="rounded-lg border border-zinc-200 bg-white p-3 text-sm">
      <summary className="cursor-pointer font-medium text-zinc-700">How to read these metrics</summary>
      <div className="mt-3 space-y-3">
        <p className="text-xs text-zinc-500">
          Two ground truths, on purpose: <b>accept-rate / precision</b> measure the <b>reviewed</b> path
          (a human approved/rejected); <b>satisfaction-rate</b> measures the <b>auto</b> path (no human,
          so the customer is the judge). <b>bar</b> = the segment&apos;s policy <code>min_confidence</code>.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-zinc-400">
              <tr>
                <th className="py-1 pr-3">Metric</th>
                <th className="py-1 pr-3">Formula</th>
                <th className="py-1">Why it matters</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.m} className="border-t border-zinc-100 align-top">
                  <td className="py-1.5 pr-3 font-medium text-zinc-700">{r.m}</td>
                  <td className="py-1.5 pr-3 font-mono text-[11px] text-zinc-600">{r.formula}</td>
                  <td className="py-1.5 text-zinc-500">{r.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-zinc-500">
          The loop: metrics <b>surface</b> a segment → readiness says if auto is <b>earned</b> → a human
          <b> grants</b> it (Promote / Add segment) → code <b>enforces</b> the ceiling.
        </p>
      </div>
    </details>
  );
}

// One segment's online-eval metrics + the promote-to-auto action. eligible_for_auto comes
// from the promotion_readiness view (≥20 reviewed-eligible, ≥0.95 accept, ≥0.97 precision).
// Promotion is still a human click — the flag just says whether the data justifies it.
function MetricCard({
  m,
  policyRow,
  onPromote,
  saving,
}: {
  m: SegmentMetric;
  policyRow?: PolicyRow;
  onPromote: (bar: number) => void;
  saving: boolean;
}) {
  const eligible = m.eligible_for_auto === true;
  const isAuto = policyRow?.approved_mode === "auto";
  const bar = policyRow?.min_confidence ?? 0.85;   // keep the segment's bar (or the view's default)

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{m.severity} · {m.category}</div>
        {isAuto ? (
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700">auto</span>
        ) : eligible ? (
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700">✓ ready</span>
        ) : (
          <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-medium text-zinc-500">not yet</span>
        )}
      </div>

      <dl className="mt-2 space-y-1 text-xs text-zinc-500">
        {Object.entries(m)
          .filter(([k]) => !["severity", "category", "eligible_for_auto"].includes(k))
          .map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt>{k}</dt>
              <dd className="tabular-nums text-zinc-700">{v == null ? "—" : String(v)}</dd>
            </div>
          ))}
      </dl>

      {!isAuto && (
        <div className="mt-3">
          <button
            disabled={saving}
            onClick={() => onPromote(bar)}
            className={cn(
              "w-full rounded px-2 py-1.5 text-xs font-medium disabled:opacity-40",
              eligible ? "bg-emerald-600 text-white" : "border border-zinc-300 text-zinc-600",
            )}
          >
            {eligible ? "Promote to auto" : "Promote to auto (override — not yet eligible)"}
          </button>
          {!eligible && (
            <p className="mt-1 text-[11px] text-zinc-400">
              Readiness: ≥3 reviewed-eligible, ≥66% accept, ≥66% precision (demo thresholds).
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// Add (or overwrite) a severity/category segment. Backend PUT /policy upserts, so the
// same call creates a new row or updates an existing one. Deny-by-default means an
// un-listed segment is 'suggest'; adding a row here is how a human GRANTS more autonomy.
function AddSegmentForm({
  existing,
  onAdd,
  saving,
}: {
  existing: PolicyRow[];
  onAdd: (r: PolicyRow) => void;
  saving: boolean;
}) {
  const [severity, setSeverity] = useState<Severity>("low");
  const [category, setCategory] = useState<string>("billing");
  const [mode, setMode] = useState<AutonomyMode>("suggest");
  const [conf, setConf] = useState("0.85");

  const dup = existing.some((r) => r.severity === severity && r.category === category);
  const confNum = parseFloat(conf);
  const valid = confNum >= 0 && confNum <= 1;

  return (
    <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-3">
      <div className="mb-2 text-sm font-medium">Add / overwrite a segment</div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-zinc-500">
          Severity
          <select value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}
            className="mt-1 block rounded border border-zinc-300 px-2 py-1 text-xs">
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="mt-1 block rounded border border-zinc-300 px-2 py-1 text-xs">
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          Approved mode
          <select value={mode} onChange={(e) => setMode(e.target.value as AutonomyMode)}
            className="mt-1 block rounded border border-zinc-300 px-2 py-1 text-xs">
            {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          Min confidence
          <input type="number" min={0} max={1} step={0.05} value={conf}
            onChange={(e) => setConf(e.target.value)}
            className="mt-1 block w-20 rounded border border-zinc-300 px-2 py-1 text-xs tabular-nums" />
        </label>
        <button
          disabled={saving || !valid}
          onClick={() => onAdd({ severity, category, approved_mode: mode, min_confidence: confNum })}
          className="rounded bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          {dup ? "Overwrite segment" : "Add segment"}
        </button>
      </div>
      {dup && (
        <p className="mt-2 text-xs text-amber-600">
          {severity}/{category} already exists — saving overwrites it.
        </p>
      )}
      {(mode === "auto" && (severity === "critical")) && (
        <p className="mt-2 text-xs text-zinc-500">
          Note: `critical` is hard-held to suggest in code — an auto policy here won&apos;t take effect.
        </p>
      )}
    </div>
  );
}

function PolicyRowEditor({
  row,
  striped,
  onSave,
  saving,
}: {
  row: PolicyRow;
  striped: boolean;
  onSave: (r: PolicyRow) => void;
  saving: boolean;
}) {
  // Local edits are uncontrolled-ish: we read the selects on save. Kept simple on purpose.
  return (
    <tr className={striped ? "bg-zinc-50/50" : ""}>
      <td className="px-3 py-2">{row.severity}</td>
      <td className="px-3 py-2">{row.category}</td>
      <td className="px-3 py-2">
        <select
          defaultValue={row.approved_mode}
          id={`mode-${row.severity}-${row.category}`}
          className="rounded border border-zinc-300 px-2 py-1 text-xs"
        >
          {MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </td>
      <td className="px-3 py-2">
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          defaultValue={row.min_confidence}
          id={`conf-${row.severity}-${row.category}`}
          className="w-20 rounded border border-zinc-300 px-2 py-1 text-xs tabular-nums"
        />
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center justify-end gap-2">
          <ModeBadge mode={row.approved_mode} />
          <button
            disabled={saving}
            onClick={() => {
              const mode = (document.getElementById(
                `mode-${row.severity}-${row.category}`,
              ) as HTMLSelectElement).value as AutonomyMode;
              const conf = parseFloat(
                (document.getElementById(`conf-${row.severity}-${row.category}`) as HTMLInputElement)
                  .value,
              );
              onSave({ ...row, approved_mode: mode, min_confidence: conf });
            }}
            className="rounded bg-zinc-900 px-2 py-1 text-xs font-medium text-white disabled:opacity-40"
          >
            Save
          </button>
        </div>
      </td>
    </tr>
  );
}

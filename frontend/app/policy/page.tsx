"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Empty, ErrorBox, Loading, ModeBadge } from "@/components/ui";
import type { AutonomyMode, PolicyRow, Severity } from "@/lib/types";

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
        {metrics.isPending && <Loading label="Loading metrics…" />}
        {metrics.isError && <ErrorBox error={metrics.error} />}
        {metrics.data?.length === 0 && <Empty label="No metrics yet." />}
        {metrics.data && metrics.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {metrics.data.map((m, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 bg-white p-3">
                <div className="text-sm font-medium">
                  {m.severity} · {m.category}
                </div>
                <dl className="mt-2 space-y-1 text-xs text-zinc-500">
                  {Object.entries(m)
                    .filter(([k]) => !["severity", "category"].includes(k))
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <dt>{k}</dt>
                        <dd className="tabular-nums text-zinc-700">{String(v)}</dd>
                      </div>
                    ))}
                </dl>
              </div>
            ))}
          </div>
        )}
      </section>
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

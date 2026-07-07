"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Button,
  Card,
  Confidence,
  Empty,
  ErrorBox,
  Loading,
  ModeBadge,
  SeverityBadge,
} from "@/components/ui";
import { cn } from "@/lib/utils";
import type { Ticket } from "@/lib/types";

type Status = "pending" | "approved" | "rejected" | "auto";
const statusOf = (t: Ticket): Status =>
  t.decision === "approve" ? "approved"
  : t.decision === "reject" ? "rejected"
  : t.recommended_mode === "auto" ? "auto"
  : "pending";

const STATUS_LABEL: Record<Status, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  auto: "Auto-resolved",
};

// Loose fuzzy: case-insensitive substring on the complaint text.
const fuzzy = (text: string, q: string) => text.toLowerCase().includes(q.trim().toLowerCase());

const COLS = "grid-cols-[2.5rem_5.5rem_7rem_1fr_4.5rem_5.5rem_6.5rem]";

export default function SupportRequestsPage() {
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => api.listTickets(200) });
  const [reviewer, setReviewer] = useState("you@versos");
  const [modeF, setModeF] = useState("all");
  const [statusF, setStatusF] = useState("all");
  const [catF, setCatF] = useState("all");
  const [q, setQ] = useState("");

  const categories = useMemo(
    () => Array.from(new Set((tickets.data ?? []).map((t) => t.category))).sort(),
    [tickets.data],
  );

  const rows = (tickets.data ?? []).filter((t) => {
    if (modeF !== "all" && t.recommended_mode !== modeF) return false;
    if (statusF !== "all" && statusOf(t) !== statusF) return false;
    if (catF !== "all" && t.category !== catF) return false;
    if (q && !fuzzy(t.complaint_text, q)) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Support Requests</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Every request — the review queue plus history. Expand a pending item to see the full
            assessment, optionally correct the remediation, and decide. Approvals feed the metrics.
          </p>
        </div>
        <label className="text-xs text-muted-foreground">
          reviewer{" "}
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="ml-1 rounded border border-input bg-background px-2 py-1 text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
      </header>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search complaints…"
          className="w-56 rounded-lg border border-input bg-background px-3 py-1.5 outline-none focus:ring-2 focus:ring-ring"
        />
        <Select label="Mode" value={modeF} onChange={setModeF} options={["all", "suggest", "approved", "auto"]} />
        <Select label="Status" value={statusF} onChange={setStatusF} options={["all", "pending", "approved", "rejected", "auto"]} />
        <Select label="Category" value={catF} onChange={setCatF} options={["all", ...categories]} />
        <span className="text-xs text-muted-foreground">{rows.length} shown</span>
      </div>

      {tickets.isPending && <Loading label="Loading…" />}
      {tickets.isError && <ErrorBox error={tickets.error} />}
      {tickets.data && rows.length === 0 && <Empty label="No requests match these filters." />}

      {rows.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          {/* Column headers */}
          <div className={cn("grid items-center gap-3 border-b border-border bg-muted/50 px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground", COLS)}>
            <span>ID</span>
            <span>Severity</span>
            <span>Category</span>
            <span>Complaint</span>
            <span>Conf.</span>
            <span>Mode</span>
            <span className="text-right">Status</span>
          </div>
          <ul className="divide-y divide-border">
            {rows.map((t) => (
              <SRRow key={t.id} ticket={t} reviewer={reviewer} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: string[];
}) {
  return (
    <label className="flex items-center gap-1 text-xs text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-input bg-background px-2 py-1.5 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const cls = {
    pending: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    rejected: "bg-red-500/15 text-red-700 dark:text-red-400",
    auto: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  }[status];
  return <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", cls)}>{STATUS_LABEL[status]}</span>;
}

function SRRow({ ticket, reviewer }: { ticket: Ticket; reviewer: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [remediation, setRemediation] = useState<string | null>(null);
  const status = statusOf(ticket);
  const actionable = status === "pending";

  const detail = useQuery({
    queryKey: ["ticket", ticket.id],
    queryFn: () => api.getTicket(ticket.id),
    enabled: open,
  });
  useEffect(() => {
    if (detail.data && remediation === null) {
      setRemediation((detail.data.developer_remediation ?? []).join("\n"));
    }
  }, [detail.data, remediation]);

  const review = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      api.review(ticket.id, {
        decision,
        reviewer,
        review_comment: "",
        final_remediation:
          decision === "approve" && remediation != null
            ? remediation.split("\n").map((s) => s.trim()).filter(Boolean)
            : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: ["ticket", ticket.id] });
    },
  });

  return (
    <li>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn("grid w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted/50", COLS)}
      >
        <span className="text-xs tabular-nums text-muted-foreground">#{ticket.id}</span>
        <SeverityBadge severity={ticket.severity} />
        <span className="truncate text-xs text-muted-foreground">{ticket.category}</span>
        <span className="truncate text-sm">{ticket.complaint_text}</span>
        <Confidence value={ticket.confidence} />
        <ModeBadge mode={ticket.recommended_mode} />
        <span className="text-right"><StatusBadge status={status} /></span>
      </button>

      {open && (
        <div className="border-t border-border bg-muted/20 p-4">
          {detail.isPending ? (
            <Loading />
          ) : detail.isError ? (
            <ErrorBox error={detail.error} />
          ) : detail.data ? (
            <div className="space-y-3 text-sm">
              <Field label="Autonomy reason">
                <span className="text-muted-foreground">{detail.data.mode_reason ?? "—"}</span>
              </Field>
              <Field label="Summary">{detail.data.summary ?? "—"}</Field>
              <Field label="Suggested customer reply (PII-masked)">
                <span className="italic text-muted-foreground">{detail.data.suggested_customer_reply || "—"}</span>
              </Field>
              <Field label={actionable ? "Developer remediation (edit to correct = the gold answer)" : "Developer remediation"}>
                {actionable ? (
                  <textarea
                    value={remediation ?? ""}
                    onChange={(e) => setRemediation(e.target.value)}
                    rows={4}
                    className="w-full resize-y rounded-lg border border-input bg-background p-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  />
                ) : (
                  <ol className="list-decimal space-y-1 pl-5">
                    {(detail.data.developer_remediation ?? []).map((s, i) => <li key={i}>{s}</li>)}
                  </ol>
                )}
              </Field>

              {actionable ? (
                <div className="flex gap-2">
                  <Button onClick={() => review.mutate("approve")} disabled={review.isPending} className="bg-emerald-600 hover:bg-emerald-700">
                    {review.isPending ? "Saving…" : "Approve"}
                  </Button>
                  <Button variant="outline" onClick={() => review.mutate("reject")} disabled={review.isPending}>
                    Reject
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {status === "auto"
                    ? "Auto-resolved by the agent — no human review needed."
                    : `Reviewed: ${ticket.decision} by ${ticket.reviewer ?? "—"}.`}
                </p>
              )}
              {review.isError && <ErrorBox error={review.error} />}
            </div>
          ) : null}
        </div>
      )}
    </li>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div>{children}</div>
    </div>
  );
}

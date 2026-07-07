"use client";

import { useEffect, useState } from "react";
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

export default function ReviewPage() {
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => api.listTickets(50) });
  const [reviewer, setReviewer] = useState("you@versos");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Agent proposals awaiting a human. Expand a ticket to see the full assessment, optionally
            correct the remediation, then decide — approvals feed the promotion metrics.
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

      {tickets.isPending && <Loading label="Loading tickets…" />}
      {tickets.isError && <ErrorBox error={tickets.error} />}
      {tickets.data?.length === 0 && <Empty label="No tickets yet. Triage one from Copilot." />}

      {tickets.data && tickets.data.length > 0 && (
        <ul className="space-y-2">
          {tickets.data.map((t) => (
            <ReviewRow key={t.id} ticket={t} reviewer={reviewer} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ReviewRow({ ticket, reviewer }: { ticket: Ticket; reviewer: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [remediation, setRemediation] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["ticket", ticket.id],
    queryFn: () => api.getTicket(ticket.id),
    enabled: open,
  });

  // Seed the editable remediation from the agent's proposal, once, when detail arrives.
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
        // On approve, send the (possibly edited) remediation as the gold answer.
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

  const reviewed = ticket.decision != null;

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 p-3 text-left transition-colors hover:bg-muted/50"
      >
        <span className="w-8 shrink-0 text-xs tabular-nums text-muted-foreground">#{ticket.id}</span>
        <SeverityBadge severity={ticket.severity} />
        <span className="hidden w-28 shrink-0 truncate text-xs text-muted-foreground sm:block">
          {ticket.category}
        </span>
        <p className="flex-1 truncate text-sm">{ticket.complaint_text}</p>
        <Confidence value={ticket.confidence} />
        <ModeBadge mode={ticket.recommended_mode} />
        <span className="w-28 shrink-0 text-right text-xs">
          {reviewed ? (
            <span
              className={cn(
                "font-medium",
                ticket.decision === "approve" ? "text-emerald-600" : "text-muted-foreground",
              )}
            >
              {ticket.decision} · {ticket.reviewer}
            </span>
          ) : (
            <span className="text-muted-foreground">{open ? "▲" : "▼ review"}</span>
          )}
        </span>
      </button>

      {open && (
        <div className="border-t border-border p-4">
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
                <span className="italic text-muted-foreground">
                  {detail.data.suggested_customer_reply || "—"}
                </span>
              </Field>
              <Field label="Developer remediation (edit to correct = the gold answer)">
                <textarea
                  value={remediation ?? ""}
                  onChange={(e) => setRemediation(e.target.value)}
                  rows={4}
                  className="w-full resize-y rounded-lg border border-input bg-background p-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="one step per line"
                />
              </Field>

              {reviewed ? (
                <p className="text-xs text-muted-foreground">
                  Reviewed: <span className="font-medium">{ticket.decision}</span> by {ticket.reviewer}
                </p>
              ) : (
                <div className="flex gap-2">
                  <Button
                    onClick={() => review.mutate("approve")}
                    disabled={review.isPending}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    {review.isPending ? "Saving…" : "Approve"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => review.mutate("reject")}
                    disabled={review.isPending}
                  >
                    Reject
                  </Button>
                </div>
              )}
              {review.isError && <ErrorBox error={review.error} />}
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div>{children}</div>
    </div>
  );
}

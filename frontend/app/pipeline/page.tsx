"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Empty,
  ErrorBox,
  Loading,
  ModeBadge,
  OutcomeBadge,
  RiskBadge,
  Stat,
  Table,
  Td,
  Th,
  Tr,
} from "@/components/ui";
import type { HealResult, PipelineJob } from "@/lib/types";

const JOB_TONE: Record<string, string> = {
  failed: "text-red-600 dark:text-red-400",
  done: "text-emerald-600 dark:text-emerald-400",
  queued: "text-amber-600 dark:text-amber-400",
  running: "text-primary",
};

export default function PipelinePage() {
  const qc = useQueryClient();
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const log = useQuery({ queryKey: ["heal-log"], queryFn: () => api.healLog(100) });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["heal-log"] });
  };
  const heal = useMutation({ mutationFn: (ref: string) => api.heal(ref), onSuccess: refresh });

  const failed = jobs.data?.filter((j) => j.status === "failed").length ?? 0;
  const resolved = log.data?.filter((h) => h.outcome === "resolved").length ?? 0;
  const escalated = log.data?.filter((h) => h.outcome === "escalated").length ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Pipeline Healer</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            A LangGraph state machine wrapped by NAT: <span className="font-mono text-xs">detect → diagnose → gate → fix / propose / escalate</span>,
            with a retry cycle. The path varies with the diagnosis; the gate still decides autonomy.
          </p>
        </div>
        <Button onClick={() => heal.mutate("")} disabled={heal.isPending || !failed}>
          {heal.isPending ? "Healing…" : `Heal all failed (${failed})`}
        </Button>
      </header>

      {heal.isError && <ErrorBox error={heal.error} />}

      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="Failed jobs" value={failed} hint={`${jobs.data?.length ?? 0} total`} />
        <Stat label="Resolved" value={resolved} hint="by the healer" />
        <Stat label="Escalated" value={escalated} hint="surfaced to a human" />
      </section>

      <Card>
        <CardHeader title="Jobs" subtitle="Stand-in for versos-processor jobs the healer acts on" />
        <CardBody>
          {jobs.isLoading ? (
            <Loading />
          ) : jobs.isError ? (
            <ErrorBox error={jobs.error} />
          ) : !jobs.data?.length ? (
            <Empty label="No jobs." />
          ) : (
            <Table
              head={
                <>
                  <Th>Job</Th>
                  <Th>Status</Th>
                  <Th>Error class</Th>
                  <Th>Attempts</Th>
                  <Th />
                </>
              }
            >
              {jobs.data.map((j: PipelineJob) => (
                <Tr key={j.id}>
                  <Td className="font-medium">{j.job_name}</Td>
                  <Td className={JOB_TONE[j.status] ?? ""}>{j.status}</Td>
                  <Td>{j.error_class ?? <span className="text-muted-foreground">—</span>}</Td>
                  <Td className="tabular-nums">{j.attempts}</Td>
                  <Td>
                    {j.status === "failed" && (
                      <Button size="sm" variant="outline" onClick={() => heal.mutate(String(j.id))} disabled={heal.isPending}>
                        Heal
                      </Button>
                    )}
                  </Td>
                </Tr>
              ))}
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Heal log" subtitle="One row per attempt — the decision log + eval dataset" />
        <CardBody>
          {log.isLoading ? (
            <Loading />
          ) : log.isError ? (
            <ErrorBox error={log.error} />
          ) : !log.data?.length ? (
            <Empty label="No heal attempts yet — run the healer." />
          ) : (
            <div className="space-y-2">
              {log.data.map((h) => (
                <HealRow key={h.id ?? `${h.job_id}-${h.created_at}`} h={h} />
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function HealRow({ h }: { h: HealResult }) {
  const [open, setOpen] = useState(false);
  const mode = h.mode ?? h.recommended_mode ?? null;
  return (
    <div className="rounded-lg border border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted/40"
      >
        <span className="font-medium">{h.job_name ?? `job ${h.job_id}`}</span>
        {h.error_class && <span className="text-xs text-muted-foreground">{h.error_class}</span>}
        {h.risk && <RiskBadge risk={h.risk} />}
        {mode && <ModeBadge mode={mode} />}
        <span className="ml-auto flex items-center gap-2">
          <OutcomeBadge outcome={h.outcome} />
          {h.log?.length ? <span className="text-xs text-muted-foreground">{open ? "▲" : "▼"}</span> : null}
        </span>
      </button>
      {open && (
        <div className="border-t border-border px-3 py-2 text-xs">
          {h.diagnosis && <p className="mb-2 text-muted-foreground">{h.diagnosis}</p>}
          {h.log?.length ? (
            <ol className="space-y-0.5 font-mono text-muted-foreground">
              {h.log.map((line, i) => (
                <li key={i}>→ {line}</li>
              ))}
            </ol>
          ) : (
            <p className="text-muted-foreground">{h.mode_reason}</p>
          )}
        </div>
      )}
    </div>
  );
}

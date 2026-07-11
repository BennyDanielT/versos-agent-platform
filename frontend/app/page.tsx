"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
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
} from "@/components/ui";

// The dashboard is the "one screen that tells the story": three verticals, one shared
// spine (assess → gate → log → evals → guardrails). Each card links into its vertical.
export default function DashboardPage() {
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => api.listTickets(100) });
  const findings = useQuery({ queryKey: ["findings"], queryFn: () => api.indexFindings(100) });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const healLog = useQuery({ queryKey: ["heal-log"], queryFn: () => api.healLog(100) });

  // auto tickets were responded to automatically → not "awaiting" a human.
  const awaiting =
    tickets.data?.filter((t) => t.decision === null && t.recommended_mode !== "auto").length ?? 0;
  const openFindings = findings.data?.filter((f) => f.decision === null).length ?? 0;
  const failedJobs = jobs.data?.filter((j) => j.status === "failed").length ?? 0;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Agent Ops Dashboard</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Three agents on one spine: each <span className="font-medium text-foreground">assesses</span>,
          a human-owned <span className="font-medium text-foreground">policy gate</span> (not the model)
          decides autonomy, every decision is logged, and destructive actions are held for a human.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Tickets logged" value={tickets.data?.length ?? "—"} hint={`${awaiting} awaiting review`} />
        <Stat label="Index findings" value={findings.data?.length ?? "—"} hint={`${openFindings} open`} />
        <Stat label="Failed jobs" value={failedJobs} hint={`${jobs.data?.length ?? 0} total`} />
        <Stat label="Heal attempts" value={healLog.data?.length ?? "—"} hint="logged" />
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        {/* Triage */}
        <Card>
          <CardHeader
            title="Support Triage"
            subtitle="Assess complaints → gate autonomy"
            action={<Link href="/copilot" className="text-xs font-medium text-primary hover:underline">Open →</Link>}
          />
          <CardBody>
            {tickets.isLoading ? (
              <Loading />
            ) : tickets.isError ? (
              <ErrorBox error={tickets.error} />
            ) : !tickets.data?.length ? (
              <Empty label="No tickets yet — run the Copilot." />
            ) : (
              <ul className="space-y-2 text-sm">
                {tickets.data.slice(0, 5).map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-2">
                    <span className="truncate text-muted-foreground">{t.complaint_text}</span>
                    <ModeBadge mode={t.recommended_mode} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* Index hygiene */}
        <Card>
          <CardHeader
            title="Index Hygiene"
            subtitle="DB optimization findings"
            action={<Link href="/index-hygiene" className="text-xs font-medium text-primary hover:underline">Open →</Link>}
          />
          <CardBody>
            {findings.isLoading ? (
              <Loading />
            ) : findings.isError ? (
              <ErrorBox error={findings.error} />
            ) : !findings.data?.length ? (
              <Empty label="No findings — run a scan." />
            ) : (
              <ul className="space-y-2 text-sm">
                {findings.data.slice(0, 5).map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span className="truncate">
                      <span className="font-medium">{f.finding_type}</span>{" "}
                      <span className="text-muted-foreground">{f.object_table}</span>
                    </span>
                    <RiskBadge risk={f.risk} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        {/* Pipeline healer */}
        <Card>
          <CardHeader
            title="Pipeline Healer"
            subtitle="Diagnose → heal failed jobs"
            action={<Link href="/pipeline" className="text-xs font-medium text-primary hover:underline">Open →</Link>}
          />
          <CardBody>
            {healLog.isLoading ? (
              <Loading />
            ) : healLog.isError ? (
              <ErrorBox error={healLog.error} />
            ) : !healLog.data?.length ? (
              <Empty label="No heal attempts yet." />
            ) : (
              <ul className="space-y-2 text-sm">
                {healLog.data.slice(0, 5).map((h) => (
                  <li key={h.id} className="flex items-center justify-between gap-2">
                    <span className="truncate text-muted-foreground">{h.job_name}</span>
                    <OutcomeBadge outcome={h.outcome} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}

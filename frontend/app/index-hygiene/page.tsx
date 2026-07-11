"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Code,
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
import type { IndexFinding } from "@/lib/types";

const REVIEWER = "ops@versos";

export default function IndexHygienePage() {
  const qc = useQueryClient();
  const findings = useQuery({ queryKey: ["findings"], queryFn: () => api.indexFindings(100) });
  const metrics = useQuery({ queryKey: ["index-metrics"], queryFn: () => api.indexMetrics() });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["findings"] });
    qc.invalidateQueries({ queryKey: ["index-metrics"] });
  };

  const scan = useMutation({ mutationFn: () => api.indexScan(), onSuccess: refresh });
  const apply = useMutation({ mutationFn: () => api.indexApply(false), onSuccess: refresh });
  const review = useMutation({
    mutationFn: (v: { id: number; decision: string }) =>
      api.reviewFinding(v.id, { decision: v.decision, reviewer: REVIEWER, review_comment: "" }),
    onSuccess: refresh,
  });

  const reclaimed = metrics.data?.reduce((s, m) => s + Number(m.bytes_reclaimed ?? 0), 0) ?? 0;
  const open = findings.data?.filter((f) => f.decision === null).length ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Index Hygiene</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            A deterministic Postgres catalog scan (no LLM — right layer for the job) finds
            unused / missing / duplicate / invalid indexes, risk-rates them, and the gate decides
            autonomy. <span className="font-medium text-foreground">DROP is destructive → never auto.</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => scan.mutate()} disabled={scan.isPending}>
            {scan.isPending ? "Scanning…" : "Run scan"}
          </Button>
          <Button onClick={() => apply.mutate()} disabled={apply.isPending}>
            {apply.isPending ? "Applying…" : "Apply approved"}
          </Button>
        </div>
      </header>

      {(scan.isError || apply.isError) && <ErrorBox error={scan.error ?? apply.error} />}

      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="Findings" value={findings.data?.length ?? "—"} hint={`${open} open`} />
        <Stat label="Bytes reclaimed" value={fmtBytes(reclaimed)} hint="from applied drops" />
        <Stat
          label="Re-create rate"
          value={metrics.data?.length ? `${maxReCreate(metrics.data)}%` : "—"}
          hint="the 'oops' signal — must be ~0 to trust auto"
        />
      </section>

      <Card>
        <CardHeader title="Findings" subtitle="Detection → risk → autonomy decision → human review" />
        <CardBody>
          {findings.isLoading ? (
            <Loading />
          ) : findings.isError ? (
            <ErrorBox error={findings.error} />
          ) : !findings.data?.length ? (
            <Empty label="No findings. Run a scan to populate the catalog." />
          ) : (
            <Table
              head={
                <>
                  <Th>Type</Th>
                  <Th>Object</Th>
                  <Th>Risk</Th>
                  <Th>Mode</Th>
                  <Th>Proposed action</Th>
                  <Th>Status</Th>
                  <Th />
                </>
              }
            >
              {findings.data.map((f) => (
                <FindingRow
                  key={f.id}
                  f={f}
                  onReview={(decision) => review.mutate({ id: f.id, decision })}
                  reviewing={review.isPending}
                />
              ))}
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function FindingRow({
  f,
  onReview,
  reviewing,
}: {
  f: IndexFinding;
  onReview: (decision: string) => void;
  reviewing: boolean;
}) {
  return (
    <Tr>
      <Td className="font-medium">{f.finding_type}</Td>
      <Td>
        <div>{f.object_table}</div>
        {f.object_index && <div className="text-xs text-muted-foreground">{f.object_index}</div>}
      </Td>
      <Td><RiskBadge risk={f.risk} /></Td>
      <Td>{f.recommended_mode ? <ModeBadge mode={f.recommended_mode} /> : "—"}</Td>
      <Td className="max-w-xs">
        {f.proposed_action ? <Code>{f.proposed_action}</Code> : <span className="text-muted-foreground">—</span>}
      </Td>
      <Td>
        {f.applied_at ? (
          <OutcomeBadge outcome="applied" />
        ) : f.decision ? (
          <span className="text-xs">{f.decision}</span>
        ) : (
          <span className="text-xs text-muted-foreground">awaiting</span>
        )}
      </Td>
      <Td>
        {!f.decision && !f.applied_at && (
          <div className="flex gap-1">
            <Button size="sm" onClick={() => onReview("approve")} disabled={reviewing}>
              Approve
            </Button>
            <Button size="sm" variant="outline" onClick={() => onReview("reject")} disabled={reviewing}>
              Reject
            </Button>
          </div>
        )}
      </Td>
    </Tr>
  );
}

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function maxReCreate(rows: { re_create_rate: number | null }[]): number {
  const r = Math.max(0, ...rows.map((x) => Number(x.re_create_rate ?? 0)));
  return Math.round(r * 100);
}

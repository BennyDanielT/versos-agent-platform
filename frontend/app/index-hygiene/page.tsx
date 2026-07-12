"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LearnDrawer } from "@/components/learn-drawer";
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
  const [learnOpen, setLearnOpen] = useState(false);
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
          <Button variant="outline" onClick={() => setLearnOpen((o) => !o)}>
            📖 Learn
          </Button>
          <Button variant="outline" onClick={() => scan.mutate()} disabled={scan.isPending}>
            {scan.isPending ? "Scanning…" : "Run scan"}
          </Button>
          <Button onClick={() => apply.mutate()} disabled={apply.isPending}>
            {apply.isPending ? "Applying…" : "Apply approved"}
          </Button>
        </div>
      </header>

      <LearnDrawer open={learnOpen} onClose={() => setLearnOpen(false)} title="Index Hygiene — study notes">
        <IndexHygieneNotes />
      </LearnDrawer>

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

// ---------------------------------------------------------------------------
// Study notes — grows lesson by lesson. Doubles as demo talking points.
// ---------------------------------------------------------------------------
function Lesson({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-sm font-semibold">
        <span className="mr-2 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">Lesson {n}</span>
        {title}
      </h3>
      <div className="mt-2 space-y-2 text-sm text-muted-foreground">{children}</div>
    </section>
  );
}

function IndexHygieneNotes() {
  return (
    <>
      <p className="text-xs text-muted-foreground">
        The system doesn&apos;t watch 3 specific tables — it inspects <b>every</b> table via Postgres&apos;s
        internal bookkeeping. Notes build up here as we go.
      </p>

      <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        <div className="mb-1 font-semibold text-foreground">Where&apos;s the &quot;agent&quot;? (agentic ≠ LLM)</div>
        <p>
          An agent = <b>sense → decide → act</b>, autonomously — an LLM is only one way to do the
          &quot;decide&quot; step. Here the agent (<code>scan_indexes</code>) <b>senses</b> by running catalog
          SQL, <b>decides</b> via risk + the policy gate, and <b>acts</b> by running DDL. The SQL is the
          agent&apos;s senses; no LLM anywhere. All three verticals share this spine but use different
          reasoning engines: triage → LLM, index → SQL, pipeline → state machine.
        </p>
      </div>

      <Lesson n={1} title="What an index is & why hygiene matters">
        <p>
          An index is like the <b>index at the back of a textbook</b>. Without it, to find every mention
          of a word you read all 900 pages (a <b>sequential scan</b>). With it, you flip to the back and
          jump straight to the right pages (an <b>index scan</b>) — much faster.
        </p>
        <p>But indexes aren&apos;t free — they&apos;re a <b>trade-off</b>:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>✅ faster <b>reads</b></li>
          <li>❌ cost <b>disk space</b> (a sorted copy of the column)</li>
          <li>❌ slow down <b>writes</b> — every INSERT/UPDATE must update every index too</li>
        </ul>
        <p>
          So a healthy database has <b>exactly the indexes it needs</b> — no more, no less. Over time
          that drifts into four problems:
        </p>
        <ul className="space-y-1">
          <li><b>unused</b> — nobody queries it → pure cost, no benefit.</li>
          <li><b>missing</b> — a big table queried with no index → slow reads.</li>
          <li><b>duplicate</b> — two indexes do the same job → double write cost.</li>
          <li><b>invalid</b> — a failed build left a broken stub taking up space.</li>
        </ul>
        <p className="rounded-lg border border-border bg-muted/40 p-2 text-xs">
          <b>Demo line:</b> &quot;An index trades slower writes and disk for faster reads. Index hygiene
          keeps that set clean — it finds the four kinds of bad index and fixes them.&quot;
        </p>
      </Lesson>

      <Lesson n={2} title="Detecting 'unused' (+ the 7-day trick)">
        <p>
          Postgres keeps its own stats. <code>pg_stat_user_indexes.idx_scan</code> = how many times an
          index has actually been used. The agent just <b>reads</b> that counter — no guessing.
        </p>
        <p>Naive rule: <b>unused = <code>idx_scan = 0</code></b> (never used → pure cost → drop it).</p>
        <p>
          <b>The trap:</b> a brand-new index <i>also</i> shows 0 scans — nobody&apos;s used it <i>yet</i>.
          Drop everything at 0 and you&apos;d kill a good index someone just made.
        </p>
        <p>
          <b>The fix — an observation window.</b> A bookkeeping table (<code>index_seen</code>) records
          when each index was <b>first seen</b>. Real rule:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li><code>idx_scan = 0</code> — never used</li>
          <li><b>AND</b> watched ≥ 7 days — old enough to trust (newborns get a grace period)</li>
          <li><b>AND</b> not unique/primary — those enforce <i>correctness</i>, not speed; never drop them</li>
        </ul>
        <p className="rounded-lg border border-border bg-muted/40 p-2 text-xs">
          <b>Demo line:</b> &quot;&apos;Unused&apos; isn&apos;t just zero scans — a new index has zero scans too. So I
          watch each index for 7 days before trusting that verdict, and I never touch unique/primary
          indexes because those enforce correctness, not speed.&quot;
        </p>
      </Lesson>

      <p className="text-xs italic text-muted-foreground">More lessons coming as we go…</p>
    </>
  );
}

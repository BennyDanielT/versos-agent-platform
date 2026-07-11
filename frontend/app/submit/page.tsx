"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button, Card, CardBody, ErrorBox, Loading } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { TriageResult } from "@/lib/types";

// Submitted requests are kept in the browser (no accounts yet) so the demo can switch between them.
type SR = { id: number; complaint: string; ts: number; mode: string };
const LS_KEY = "versos_srs";

// Why the request wasn't turned into a ticket. `null` = it was.
type Notice = "off_topic" | "blocked" | null;

// A guardrail/input-rail refusal (as opposed to a triage failure). Both come back as
// HTTP 200 with no ticket_id, so the summary is what tells them apart.
const isBlocked = (res: TriageResult) => (res.summary ?? "").startsWith("Rejected");
const loadSRs = (): SR[] => {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) ?? "[]");
  } catch {
    return [];
  }
};

const SAMPLES: { label: string; text: string }[] = [
  { label: "Minor bug", text: "The editor keeps forgetting my dark-mode preference between sessions — minor, but annoying." },
  { label: "Media quality", text: "My exported 1080p video is blurry and over-compressed compared to the preview." },
  { label: "Account locked", text: "I'm completely locked out of my account and the password reset email never arrives." },
];

export default function SubmitPage() {
  const [text, setText] = useState("");
  const [srs, setSrs] = useState<SR[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  useEffect(() => setSrs(loadSRs()), []);

  const submit = useMutation({
    mutationFn: async (c: string) => {
      const res = await api.triage(c);
      // The backend returns 200 with NO ticket_id on three paths: the regex guardrail,
      // the NeMo input rail, and an LLM/structured-output failure. The first two are a
      // deliberate "we won't accept this"; the third is a real error. Previously all
      // three fell through to a silent no-op, so Submit looked broken.
      if (res.is_support_request !== false && !res.ticket_id && !isBlocked(res)) {
        throw new Error("We couldn't process your request just now. Please try again in a moment.");
      }
      return res;
    },
    onSuccess: (res: TriageResult) => {
      if (res.is_support_request === false) {
        setNotice("off_topic"); // don't store off-topic as a request
        return;
      }
      if (!res.ticket_id) {
        setNotice("blocked"); // guardrail / input rail refused it
        return;
      }
      setNotice(null);
      const sr: SR = { id: res.ticket_id, complaint: text.trim(), ts: Date.now(), mode: res.recommended_mode };
      setSrs((prev) => {
        const next = [sr, ...prev].slice(0, 50);
        localStorage.setItem(LS_KEY, JSON.stringify(next));
        return next;
      });
      setSelected(res.ticket_id);
      setText("");
    },
  });

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      {/* Left: submitted requests */}
      <aside className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Your requests
        </h2>
        {srs.length === 0 ? (
          <p className="text-sm text-muted-foreground">None yet — submit one.</p>
        ) : (
          <ul className="space-y-1">
            {srs.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => setSelected(s.id)}
                  className={cn(
                    "w-full rounded-lg border p-2 text-left text-sm transition-colors",
                    selected === s.id
                      ? "border-primary bg-accent"
                      : "border-border hover:bg-muted/50",
                  )}
                >
                  <div className="truncate">{s.complaint}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">#{s.id}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* Right: form + selected request */}
      <div className="space-y-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">How can we help?</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Describe your issue and our support assistant will respond.
          </p>
        </header>

        <Card>
          <CardBody className="space-y-3">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              placeholder="Tell us what's going on…"
              className="w-full resize-y rounded-lg border border-input bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => submit.mutate(text)} disabled={submit.isPending || text.trim().length < 3}>
                {submit.isPending ? "Sending…" : "Submit request"}
              </Button>
              <span className="text-xs text-muted-foreground">Try:</span>
              {SAMPLES.map((s) => (
                <Button key={s.label} variant="outline" size="sm" onClick={() => setText(s.text)}>
                  {s.label}
                </Button>
              ))}
            </div>
          </CardBody>
        </Card>

        {submit.isError && <ErrorBox error={submit.error} />}
        {notice === "off_topic" && (
          <Card className="border-border bg-muted/40">
            <CardBody className="text-sm text-muted-foreground">
              That doesn&apos;t look like a product request. We help with our video product — accounts,
              exports, media quality, and billing. Add a few details and resend.
            </CardBody>
          </Card>
        )}
        {notice === "blocked" && (
          <Card className="border-amber-500/40 bg-amber-500/10">
            <CardBody className="text-sm text-muted-foreground">
              We couldn&apos;t accept that message. Please describe your issue with our product in your
              own words and resend.
            </CardBody>
          </Card>
        )}

        {selected != null && <SRView id={selected} />}
      </div>
    </div>
  );
}

function SRView({ id }: { id: number }) {
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["ticket", id], queryFn: () => api.getTicket(id) });
  const csat = useMutation({
    mutationFn: (satisfied: boolean) => api.csat(id, satisfied),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ticket", id] }),
  });
  const escalate = useMutation({
    mutationFn: (followup?: string) => api.escalate(id, followup),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ticket", id] });
      qc.invalidateQueries({ queryKey: ["tickets"] });
    },
  });

  if (detail.isPending) return <Loading />;
  if (detail.isError) return <ErrorBox error={detail.error} />;
  const t = detail.data!;
  const reviewed = t.decision === "approve";
  const rejected = t.decision === "reject";
  const isAuto = t.recommended_mode === "auto" && !reviewed && !rejected;
  // The message that actually goes to the customer: the specialist's edit, else the model's draft.
  const reply = t.final_customer_reply || t.suggested_customer_reply || "—";
  // Re-opened: there's a prior specialist reply but it's back in the queue awaiting another look.
  const reopened = !reviewed && !rejected && !isAuto && !!t.final_customer_reply;

  return (
    <Card
      className={cn(
        reviewed
          ? "border-emerald-500/40 bg-emerald-500/10"
          : rejected
            ? "border-red-500/40 bg-red-500/10"
            : isAuto
              ? "border-border"
              : "border-blue-500/40 bg-blue-500/10",
      )}
    >
      <CardBody className="space-y-3">
        {rejected ? (
          <>
            <div className="text-sm font-semibold">Request reviewed — closed (rejected)</div>
            <p className="text-sm text-muted-foreground">
              A specialist reviewed this request and closed it. If you think this was a mistake, add
              any detail below and we&apos;ll take another look.
            </p>
            <EscalateBox
              prompt="Disagree with this outcome? Add context and we'll re-open it."
              cta="Re-open request"
              pending={escalate.isPending}
              onSend={(msg) => escalate.mutate(msg)}
            />
          </>
        ) : reviewed ? (
          <>
            <div className="text-sm font-semibold">A specialist has responded</div>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">{reply}</p>
            <EscalateBox
              prompt="Still need help? Send a follow-up and we'll take another look."
              cta="Send follow-up"
              pending={escalate.isPending}
              onSend={(msg) => escalate.mutate(msg)}
            />
          </>
        ) : isAuto ? (
          <>
            <div className="text-sm font-semibold">Response from our assistant</div>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">{reply}</p>
            <p className="text-xs text-muted-foreground">
              If this doesn&apos;t resolve your concern, escalate it and a specialist will review it.
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {t.customer_satisfied == null ? (
                <>
                  <span className="text-xs text-muted-foreground">Did this help?</span>
                  <Button variant="outline" size="sm" onClick={() => csat.mutate(true)} disabled={csat.isPending}>
                    👍 Yes
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => csat.mutate(false)} disabled={csat.isPending}>
                    👎 No
                  </Button>
                </>
              ) : (
                <span className="text-xs text-muted-foreground">
                  Thanks for your feedback{t.customer_satisfied ? " 👍" : " 👎"}.
                </span>
              )}
            </div>
            <EscalateBox
              prompt="Prefer a human? Add any detail and a specialist will review it."
              cta="Escalate for review"
              pending={escalate.isPending}
              onSend={(msg) => escalate.mutate(msg)}
            />
          </>
        ) : reopened ? (
          <>
            <div className="text-sm font-semibold">We&apos;re taking another look</div>
            <p className="text-sm text-muted-foreground">
              Thanks for the follow-up — a specialist will get back to you. Their previous reply:
            </p>
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2 text-sm text-muted-foreground">
              {reply}
            </p>
          </>
        ) : (
          <>
            <div className="text-sm font-semibold">We&apos;re on it</div>
            <p className="text-sm text-muted-foreground">
              Your request is with our team and a specialist will follow up soon.
            </p>
          </>
        )}
      </CardBody>
    </Card>
  );
}

// A small compose box: optional message + a button that escalates / re-opens the ticket.
function EscalateBox({
  prompt,
  cta,
  pending,
  onSend,
}: {
  prompt: string;
  cta: string;
  pending: boolean;
  onSend: (msg: string) => void;
}) {
  const [msg, setMsg] = useState("");
  return (
    <div className="space-y-2 border-t border-border/60 pt-3">
      <p className="text-xs text-muted-foreground">{prompt}</p>
      <textarea
        value={msg}
        onChange={(e) => setMsg(e.target.value)}
        rows={2}
        placeholder="Add a detail (optional)…"
        className="w-full resize-y rounded-lg border border-input bg-background p-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      <Button size="sm" onClick={() => onSend(msg.trim())} disabled={pending}>
        {pending ? "Sending…" : cta}
      </Button>
    </div>
  );
}

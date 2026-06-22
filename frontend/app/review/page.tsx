"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { Confidence, Empty, ErrorBox, Loading, ModeBadge, SeverityBadge } from "@/components/ui";
import type { Ticket } from "@/lib/types";

export default function ReviewPage() {
  const qc = useQueryClient();
  const tickets = useQuery({ queryKey: ["tickets"], queryFn: () => api.listTickets(50) });
  const [reviewer, setReviewer] = useState("you@versos");

  const review = useMutation({
    mutationFn: (v: { id: number; decision: "approve" | "reject" }) =>
      api.review(v.id, { decision: v.decision, reviewer, review_comment: "" }),
    // Optimistic but honest: flip the row immediately, roll back if the server rejects.
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: ["tickets"] });
      const prev = qc.getQueryData<Ticket[]>(["tickets"]);
      qc.setQueryData<Ticket[]>(["tickets"], (old) =>
        old?.map((t) => (t.id === v.id ? { ...t, decision: v.decision, reviewer } : t)),
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(["tickets"], ctx.prev),
    onSettled: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Review queue</h1>
          <p className="text-sm text-zinc-500">
            Agent proposals awaiting a human. Approving is the human-in-the-loop control the
            autonomy gate defers to.
          </p>
        </div>
        <label className="text-xs text-zinc-500">
          reviewer{" "}
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="ml-1 rounded border border-zinc-300 px-2 py-1 text-zinc-700"
          />
        </label>
      </header>

      {tickets.isPending && <Loading label="Loading tickets…" />}
      {tickets.isError && <ErrorBox error={tickets.error} />}
      {tickets.data?.length === 0 && <Empty label="No tickets yet. Triage one from Copilot." />}

      {tickets.data && tickets.data.length > 0 && (
        <ul className="space-y-2">
          {tickets.data.map((t) => (
            <li
              key={t.id}
              className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white p-3"
            >
              <span className="w-10 text-xs tabular-nums text-zinc-400">#{t.id}</span>
              <SeverityBadge severity={t.severity} />
              <span className="w-28 truncate text-xs text-zinc-500">{t.category}</span>
              <p className="flex-1 truncate text-sm">{t.complaint_text}</p>
              <Confidence value={t.confidence} />
              <ModeBadge mode={t.recommended_mode} />
              <div className="w-32 text-right">
                {t.decision ? (
                  <span className="text-xs font-medium text-zinc-500">
                    {t.decision} · {t.reviewer}
                  </span>
                ) : (
                  <div className="flex justify-end gap-1">
                    <button
                      onClick={() => review.mutate({ id: t.id, decision: "approve" })}
                      className="rounded bg-emerald-600 px-2 py-1 text-xs font-medium text-white"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => review.mutate({ id: t.id, decision: "reject" })}
                      className="rounded border border-zinc-300 px-2 py-1 text-xs"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {review.isError && <ErrorBox error={review.error} />}
    </div>
  );
}

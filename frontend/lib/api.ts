// One typed client. Every call goes through the Next.js proxy at /api/* (see
// app/api/[...path]/route.ts), so the browser never knows the backend URL.
import type {
  AskResponse,
  PolicyRow,
  SegmentMetric,
  Ticket,
  TriageResult,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    // Surface the backend's detail message so the UI shows a real reason, not "Error".
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  triage: (complaint: string) =>
    req<TriageResult>("triage", {
      method: "POST",
      body: JSON.stringify({ complaint }),
    }),

  ask: (message: string) =>
    req<AskResponse>("ask", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  listTickets: (limit = 50) => req<Ticket[]>(`tickets?limit=${limit}`),
  getTicket: (id: number) => req<Ticket>(`tickets/${id}`),

  review: (id: number, body: { decision: string; reviewer: string; review_comment: string }) =>
    req<{ status: string }>(`tickets/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  policy: () => req<PolicyRow[]>("policy"),
  upsertPolicy: (body: PolicyRow & { updated_by: string }) =>
    req<{ status: string }>("policy", { method: "PUT", body: JSON.stringify(body) }),

  metrics: () => req<SegmentMetric[]>("metrics"),
};

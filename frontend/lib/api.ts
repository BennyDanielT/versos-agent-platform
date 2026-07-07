// One typed client. Every call goes through the Next.js proxy at /api/* (see
// app/api/[...path]/route.ts), so the browser never knows the backend URL.
import type {
  AskResponse,
  HealPolicyRow,
  HealResult,
  IndexFinding,
  IndexMetric,
  IndexPolicyRow,
  PipelineJob,
  PolicyRow,
  SimConfig,
  SimStatus,
  SegmentMetric,
  SystemFlag,
  Ticket,
  TicketDetail,
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
  getTicket: (id: number) => req<TicketDetail>(`tickets/${id}`),

  review: (
    id: number,
    body: { decision: string; reviewer: string; review_comment: string; final_remediation?: string[] },
  ) =>
    req<{ status: string }>(`tickets/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  csat: (id: number, satisfied: boolean) =>
    req<{ status: string }>(`tickets/${id}/csat`, {
      method: "POST",
      body: JSON.stringify({ satisfied }),
    }),
  escalate: (id: number) =>
    req<{ status: string }>(`tickets/${id}/escalate`, { method: "POST", body: "{}" }),

  policy: () => req<PolicyRow[]>("policy"),
  upsertPolicy: (body: PolicyRow & { updated_by: string }) =>
    req<{ status: string }>("policy", { method: "PUT", body: JSON.stringify(body) }),

  metrics: () => req<SegmentMetric[]>("metrics"),

  // --- index hygiene ---
  indexFindings: (limit = 100) => req<IndexFinding[]>(`index/findings?limit=${limit}`),
  indexMetrics: () => req<IndexMetric[]>("index/metrics"),
  indexPolicy: () => req<IndexPolicyRow[]>("index/policy"),
  indexScan: () =>
    req<{ count: number; findings: IndexFinding[] }>("index/scan", { method: "POST", body: "{}" }),
  indexApply: (allow_auto = false) =>
    req<{ applied: unknown[] }>("index/apply", {
      method: "POST",
      body: JSON.stringify({ allow_auto }),
    }),
  reviewFinding: (id: number, body: { decision: string; reviewer: string; review_comment: string }) =>
    req<{ status: string }>(`index/findings/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // --- pipeline healer ---
  jobs: () => req<PipelineJob[]>("pipeline/jobs"),
  healLog: (limit = 100) => req<HealResult[]>(`pipeline/heal-log?limit=${limit}`),
  healPolicy: () => req<HealPolicyRow[]>("pipeline/policy"),
  heal: (job_ref = "") =>
    req<{ healed: HealResult[] }>("pipeline/heal", {
      method: "POST",
      body: JSON.stringify({ job_ref }),
    }),

  // --- simulator ---
  simStatus: () => req<SimStatus>("sim/status"),
  simStart: (cfg: Partial<SimConfig> = {}) =>
    req<SimStatus>("sim/start", { method: "POST", body: JSON.stringify(cfg) }),
  simStop: () => req<SimStatus>("sim/stop", { method: "POST", body: "{}" }),
  simConfig: (cfg: Partial<SimConfig>) =>
    req<SimStatus>("sim/config", { method: "POST", body: JSON.stringify(cfg) }),

  // --- admin: live runtime flags (kill switch + guardrail toggles) ---
  flags: () => req<SystemFlag[]>("admin/flags"),
  setFlag: (name: string, enabled: boolean) =>
    req<SystemFlag>("admin/flags", {
      method: "POST",
      body: JSON.stringify({ name, enabled, updated_by: "console" }),
    }),
};

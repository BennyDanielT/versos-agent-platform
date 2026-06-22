// Types mirror the FastAPI contract (backend/schemas.py + the triage tool's JSON).
//
// In a longer-lived project these would be GENERATED from the backend's /openapi.json
// via `openapi-typescript`, so frontend and backend can never silently drift. For the
// interview scope they're hand-written but kept faithful to the contract — say that out
// loud: "contract-first; I'd generate these from openapi.json in a real project."

export type AutonomyMode = "suggest" | "approved" | "auto";
export type Severity = "low" | "medium" | "high" | "critical";

// Returned by POST /triage — the assessment AND the explanation of the autonomy decision.
export interface TriageResult {
  severity: Severity;
  category: string;
  confidence: number;                 // 0..1
  summary: string;
  developer_remediation: string[];
  suggested_customer_reply: string;
  recommended_mode: AutonomyMode;     // what the gate landed on
  mode_reason: string;                // WHY it landed there — the explainability hero
}

// Rows from GET /tickets (the triage_log decision log).
export interface Ticket {
  id: number;
  complaint_text: string;
  severity: Severity;
  category: string;
  confidence: number;
  recommended_mode: AutonomyMode;
  decision: string | null;            // null = awaiting human review
  reviewer: string | null;
  created_at: string;
}

// Per-segment autonomy policy from GET /policy.
export interface PolicyRow {
  severity: Severity;
  category: string;
  approved_mode: AutonomyMode;
  min_confidence: number;
  updated_by?: string;
}

export interface SegmentMetric {
  severity: Severity;
  category: string;
  total: number;
  auto_rate?: number;
  [k: string]: unknown;               // metrics view is wide; render defensively
}

export interface AskResponse {
  answer: string;
}

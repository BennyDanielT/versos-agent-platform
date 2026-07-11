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
  is_support_request?: boolean;       // false = off-topic / not a real support request (flagged)
  ticket_id?: number;                 // triage_log id (for CSAT / escalate)
}

// A runtime feature flag row from GET /admin/flags (the system_flags table).
export interface SystemFlag {
  name: string;
  enabled: boolean;
  updated_by: string | null;
  updated_at: string;
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
  customer_satisfied?: boolean | null; // CSAT on the (auto) reply
  created_at: string;
}

// The full row from GET /tickets/{id} (SELECT * — includes the assessment fields).
export interface TicketDetail extends Ticket {
  summary?: string;
  developer_remediation?: string[];
  suggested_customer_reply?: string;
  mode_reason?: string;
  final_remediation?: string[] | null;
  final_customer_reply?: string | null;   // dev's edited customer reply (what actually goes out)
  review_comment?: string | null;
  customer_followup?: string | null;       // latest client follow-up when re-opened
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

export type Risk = "low" | "medium" | "high";

// ---- Index hygiene (GET /index/findings) --------------------------------
export interface IndexFinding {
  id: number;
  finding_type: string;               // unused | missing | duplicate | invalid
  object_table: string;
  object_index: string | null;
  detail: Record<string, unknown> | null;
  risk: Risk;
  proposed_action: string | null;
  rollback_action: string | null;
  recommended_mode: AutonomyMode | null;
  mode_reason: string | null;
  detected_at: string;
  decision: string | null;            // null = awaiting review
  reviewer: string | null;
  applied_at: string | null;
  outcome: Record<string, unknown> | null;
}

export interface IndexMetric {
  finding_type: string;
  applied: number;
  bytes_reclaimed: number;
  re_created: number;
  re_create_rate: number | null;
}

export interface IndexPolicyRow {
  finding_type: string;
  risk: Risk;
  approved_mode: AutonomyMode;
  updated_by: string | null;
  updated_at: string;
}

// ---- Pipeline healer -----------------------------------------------------
export interface PipelineJob {
  id: number;
  job_name: string;
  status: string;                     // queued | running | failed | done
  error_class: string | null;
  locked_by: string | null;
  attempts: number;
  updated_at: string;
}

// One row per healing attempt, returned by POST /pipeline/heal and GET /pipeline/heal-log.
export interface HealResult {
  id?: number;                        // present on heal-log rows, absent on live heal results
  job_id: number;
  job_name: string | null;
  error_class: string | null;
  diagnosis: string | null;
  fix_type: string | null;
  risk: Risk | null;
  mode?: AutonomyMode | null;         // heal endpoint
  recommended_mode?: AutonomyMode | null; // heal-log rows
  mode_reason: string | null;
  action_taken?: string | null;
  outcome: string | null;             // resolved | proposed | escalated | skipped
  attempts: number;
  log?: string[];
  created_at?: string;
}

export interface HealPolicyRow {
  fix_type: string;
  risk: Risk;
  approved_mode: AutonomyMode;
  updated_by: string | null;
  updated_at: string;
}

// ---- Simulator -----------------------------------------------------------
export interface SimConfig {
  speed: number;
  triage_enabled: boolean;
  triage_per_min: number;
  pipeline_enabled: boolean;
  jobs_per_min: number;
  job_fail_rate: number;
  auto_heal: boolean;
  index_enabled: boolean;
  index_ops_per_min: number;
  auto_scan: boolean;
}

export interface SimStats {
  started_at: number | null;
  uptime_sec: number;
  triage_done: number;
  triage_errors: number;
  jobs_created: number;
  jobs_processed: number;
  jobs_failed: number;
  heals: number;
  index_ops: number;
  scans: number;
  errors: number;
}

export interface SimStatus {
  running: boolean;
  config: SimConfig;
  stats: SimStats;
}

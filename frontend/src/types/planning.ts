export type SourceMode = "live" | "mixed" | "stale" | "manual" | "fixture" | "unavailable";

export type SegmentType =
  | "intercity_transport"
  | "local_transport"
  | "visit"
  | "lodging"
  | "meal_allowance"
  | "buffer";

export type PolicyStatus = "pass" | "fail" | "warning";
export type RevisionStatus = "proposed" | "active" | "superseded" | "rejected";

export interface PlanSegment {
  segment_id: string;
  segment_type: SegmentType;
  title: string;
  from_ref?: string | null;
  to_ref?: string | null;
  start_at: string;
  end_at: string;
  cost_yuan: number;
  provider: string;
  source_mode: SourceMode;
  candidate_id?: string | null;
  task_id?: string | null;
  metadata: Record<string, unknown>;
}

export interface CostLedger {
  intercity_transport_yuan: number;
  local_transport_yuan: number;
  lodging_yuan: number;
  meals_yuan: number;
  planned_total_yuan: number;
  policy_total_cap_yuan: number;
  remaining_yuan: number;
}

export interface PolicyDecision {
  rule_id: string;
  status: PolicyStatus;
  observed: string;
  limit: string;
  explanation: string;
}

export interface ScoreBreakdown {
  lateness_risk: number;
  cost: number;
  transfer_burden: number;
  walking: number;
  policy_margin: number;
  total: number;
}

export interface PlanOption {
  option_id: string;
  label: string;
  summary: string;
  segments: PlanSegment[];
  costs: CostLedger;
  policy_decisions: PolicyDecision[];
  score: ScoreBreakdown;
  warnings: string[];
}

export interface PlanBundle {
  mission_id: string;
  preferred_option_id: string;
  options: PlanOption[];
  provider_snapshot_ids: string[];
  generated_at: string;
  planner_version: string;
  verifier_version: string;
}

export interface PlanGenerationRequest {
  request_id: string;
  based_on_revision?: number | null;
  input_event_id?: string | null;
}

export interface PlanRevision {
  revision_id: string;
  mission_id: string;
  revision: number;
  based_on_revision?: number | null;
  request_id: string;
  input_event_id?: string | null;
  status: RevisionStatus;
  bundle: PlanBundle;
  idempotent_replay: boolean;
  created_at: string;
}

export interface SegmentChange {
  identity: string;
  change_type: "added" | "removed" | "changed";
  before?: PlanSegment | null;
  after?: PlanSegment | null;
}

export interface RevisionDiff {
  mission_id: string;
  from_revision: number;
  to_revision: number;
  input_event_id?: string | null;
  changes: SegmentChange[];
  preserved_segment_count: number;
  cost_delta_yuan: number;
  score_delta: number;
  warnings_added: string[];
  warnings_removed: string[];
}

export interface RevisionActivationReceipt {
  mission_id: string;
  active_revision: number;
  status: RevisionStatus;
  idempotent_replay: boolean;
}

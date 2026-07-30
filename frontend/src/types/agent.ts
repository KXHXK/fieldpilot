export type AgentMode = "mock" | "live" | "fallback";
export type InterpretationStatus = "ready" | "needs_clarification";

export interface ClarificationQuestion {
  field: string;
  question: string;
  reason: string;
}

export interface AgentTrace {
  trace_id: string;
  mode: AgentMode;
  model: string;
  prompt_version: string;
  latency_ms: number;
  request_count: number;
  input_tokens: number | null;
  output_tokens: number | null;
  tool_calls: 0;
  failure_type: string | null;
  idempotent_replay: boolean;
}

export interface InterpretMissionResponse {
  status: InterpretationStatus;
  ready_for_submission: boolean;
  draft: MissionDraft;
  clarifications: ClarificationQuestion[];
  safety_flags: string[];
  confidence: number;
  trace: AgentTrace;
}

export interface MissionDraft {
  origin: { name: string | null; address: string | null; city: string | null };
  destination_city: string | null;
  start_date: string | null;
  end_date: string | null;
  timezone: string;
  urgency: "tight" | "balanced" | "flexible";
  visits: Array<{
    name: string | null;
    address: string | null;
    city: string | null;
    window_start: string | null;
    window_end: string | null;
    duration_minutes: number | null;
    priority: string;
    notes: string;
  }>;
  expense_policy: {
    policy_id: string;
    policy_version: string;
    allowed_rail_classes: string[] | null;
    allowed_flight_classes: string[] | null;
    hotel_nightly_cap_yuan: number | null;
    meal_daily_cap_yuan: number | null;
    local_transport_daily_cap_yuan: number | null;
    trip_total_cap_yuan: number | null;
  };
  preferred_intercity_modes: string[];
  preferred_local_modes: string[];
  notes: string;
}

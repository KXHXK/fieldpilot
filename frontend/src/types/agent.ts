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
  draft: Record<string, unknown>;
  clarifications: ClarificationQuestion[];
  safety_flags: string[];
  confidence: number;
  trace: AgentTrace;
}

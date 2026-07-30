export type Urgency = "tight" | "balanced" | "flexible";

export type MissionStatus =
  | "draft"
  | "needs_input"
  | "planning"
  | "ready"
  | "active"
  | "replan_pending"
  | "completed"
  | "cancelled";

export type VisitPriority = "required" | "high" | "normal" | "optional";

export type ReplanEventType =
  | "task_rescheduled"
  | "task_cancelled"
  | "task_added"
  | "task_extended"
  | "budget_changed"
  | "preference_changed"
  | "transport_disruption"
  | "weather_risk";

export interface MissionLocation {
  name: string;
  address: string;
  city: string;
  longitude?: number | null;
  latitude?: number | null;
}

export interface VisitTaskInput {
  name: string;
  location: MissionLocation;
  window_start: string;
  window_end: string;
  duration_minutes: number;
  priority: VisitPriority;
  locked: boolean;
  notes: string;
}

export interface VisitTask extends VisitTaskInput {
  task_id: string;
  position: number;
  completed: boolean;
}

export interface TransportPreferences {
  preferred_intercity_modes: string[];
  preferred_local_modes: string[];
  minimum_transfer_minutes: number;
  allow_early_arrival_day: boolean;
}

export interface ExpensePolicyInput {
  policy_id: string;
  policy_version: string;
  allowed_rail_classes: string[];
  allowed_flight_classes: string[];
  hotel_nightly_cap_yuan: number;
  meal_daily_cap_yuan: number;
  local_transport_daily_cap_yuan: number;
  trip_total_cap_yuan: number;
}

export interface ExpensePolicySnapshot extends ExpensePolicyInput {
  snapshot_id: string;
}

export interface MissionCreate {
  origin: MissionLocation;
  start_date: string;
  end_date: string;
  timezone: string;
  urgency: Urgency;
  visits: VisitTaskInput[];
  expense_policy: ExpensePolicyInput;
  transport_preferences: TransportPreferences;
  notes: string;
}

export interface Mission extends Omit<MissionCreate, "visits" | "expense_policy"> {
  mission_id: string;
  status: MissionStatus;
  active_revision?: number | null;
  visits: VisitTask[];
  expense_policy: ExpensePolicySnapshot;
  created_at: string;
  updated_at: string;
}

export interface ReplanEventCreate {
  event_id: string;
  event_type: ReplanEventType;
  based_on_revision?: number | null;
  payload: Record<string, unknown>;
}

export interface ReplanEventReceipt {
  event_id: string;
  mission_id: string;
  event_type: ReplanEventType;
  based_on_revision?: number | null;
  accepted: boolean;
  idempotent_replay: boolean;
  created_at: string;
}

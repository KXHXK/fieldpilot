export interface GeoPoint {
  longitude: number;
  latitude: number;
}

export interface FieldTaskRequest {
  city: string;
  start_date: string;
  end_date: string;
  industry: string;
  target_place_types: string[];
  objective: string;
  budget: number;
  transport_type: "public_transport" | "taxi" | "walking";
  base_preference: string;
}

export interface TargetPlace {
  target_id: string;
  name: string;
  category: string;
  address: string;
  location: GeoPoint;
  task_brief: string;
  evidence_source: "synthetic" | "amap";
  source_reference?: string | null;
}

export interface FieldRisk {
  date: string;
  level: "low" | "medium" | "high";
  weather_summary: string;
  execution_risk: string;
  mitigation: string;
  evidence_source: "synthetic" | "tavily";
}

export interface OperationBase {
  name: string;
  address: string;
  location: GeoPoint;
  rationale: string;
  estimated_nightly_cost: number;
}

export interface DailyFieldPlan {
  day_index: number;
  date: string;
  summary: string;
  transport_guidance: string;
  base_guidance: string;
  risk_level: "low" | "medium" | "high";
  targets: TargetPlace[];
}

export interface CostBreakdown {
  target_operations: number;
  lodging: number;
  meals: number;
  transportation: number;
  planned_total: number;
  budget_limit: number;
  remaining: number;
}

export interface ToolStatus {
  tool: string;
  status: "success" | "mock" | "degraded";
  detail: string;
  elapsed_ms: number;
}

export interface FieldTaskPlan {
  task_id: string;
  city: string;
  start_date: string;
  end_date: string;
  industry: string;
  objective: string;
  overview: string;
  operation_base: OperationBase;
  risks: FieldRisk[];
  days: DailyFieldPlan[];
  costs: CostBreakdown;
  tool_statuses: ToolStatus[];
  warnings: string[];
  generated_at: string;
  map_image_url?: string | null;
}

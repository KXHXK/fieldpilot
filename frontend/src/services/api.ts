import type { InterpretMissionResponse } from "../types/agent";
import type { Mission, MissionCreate, ReplanEventCreate, ReplanEventReceipt } from "../types/mission";
import type { ExecutionCheckpoint, ExecutionCheckpointCommand, PlanGenerationRequest, PlanRevision, RevisionActivationReceipt, RevisionDiff } from "../types/planning";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  local_route_provider: string;
  agent_mode: "mock" | "live";
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("；")
      : typeof payload?.detail === "string"
        ? payload.detail
        : payload?.detail?.message || payload?.detail?.code;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const checkHealth = () => request<HealthResponse>("/health");

export const interpretMission = (text: string, referenceDate: string) =>
  request<InterpretMissionResponse>("/v1/agent/interpret-mission", {
    method: "POST",
    body: JSON.stringify({
      request_id: `agent-${crypto.randomUUID()}`,
      text,
      reference_date: referenceDate,
      timezone: "Asia/Shanghai"
    })
  });

export const createMission = (mission: MissionCreate) =>
  request<Mission>("/v1/missions", { method: "POST", body: JSON.stringify(mission) });

export const getMission = (missionId: string) =>
  request<Mission>(`/v1/missions/${missionId}`);

export const generatePlan = (missionId: string, command: PlanGenerationRequest) =>
  request<PlanRevision>(`/v1/missions/${missionId}/plans`, {
    method: "POST",
    body: JSON.stringify(command)
  });

export const activateRevision = (missionId: string, revision: number, expected: number | null) =>
  request<RevisionActivationReceipt>(`/v1/missions/${missionId}/revisions/${revision}/activate`, {
    method: "POST",
    body: JSON.stringify({ expected_active_revision: expected })
  });

export const createReplanEvent = (missionId: string, event: ReplanEventCreate) =>
  request<ReplanEventReceipt>(`/v1/missions/${missionId}/events`, {
    method: "POST",
    body: JSON.stringify(event)
  });

export const diffRevisions = (missionId: string, fromRevision: number, toRevision: number) =>
  request<RevisionDiff>(`/v1/missions/${missionId}/revisions/${fromRevision}/diff/${toRevision}`);

export const getExecutionCheckpoint = (missionId: string) =>
  request<ExecutionCheckpoint>(`/v1/missions/${missionId}/execution`);

export const advanceExecutionCheckpoint = (missionId: string, command: ExecutionCheckpointCommand) =>
  request<ExecutionCheckpoint>(`/v1/missions/${missionId}/execution/checkpoints`, {
    method: "POST",
    body: JSON.stringify(command)
  });

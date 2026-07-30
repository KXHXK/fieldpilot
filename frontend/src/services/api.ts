import type { FieldTaskPlan, FieldTaskRequest } from "../types/field";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function checkHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export async function createFieldTaskPlan(request: FieldTaskRequest): Promise<FieldTaskPlan> {
  const response = await fetch(`${API_BASE_URL}/field-task/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("；")
      : payload?.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

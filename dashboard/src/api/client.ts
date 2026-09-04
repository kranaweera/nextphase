import type {
  AlertRecordOut,
  AlertRuleRecord,
  AlertStatus,
  Baseline,
  EventRecordOut,
  MetricCategory,
  MetricPoint,
  SessionDetailRecord,
  SessionSummary,
} from "../types";

const BASE = "/api";

async function request<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const query = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) query.set(key, String(value));
    }
  }
  const qs = query.toString();
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function listSessions(modelName?: string): Promise<SessionSummary[]> {
  return request("/sessions", { model_name: modelName });
}

export function getSession(sessionId: string): Promise<SessionDetailRecord> {
  return request(`/sessions/${sessionId}`);
}

export function getBaseline(sessionId: string): Promise<Baseline> {
  return request(`/sessions/${sessionId}/baseline`);
}

export function getEvents(sessionId: string, limit = 100): Promise<EventRecordOut[]> {
  return request(`/sessions/${sessionId}/events`, { limit });
}

export function getMetrics(
  sessionId: string,
  category?: MetricCategory,
): Promise<MetricPoint[]> {
  return request(`/sessions/${sessionId}/metrics`, { category });
}

export function listAlerts(sessionId?: string, status?: AlertStatus): Promise<AlertRecordOut[]> {
  return request("/alerts", { session_id: sessionId, status });
}

export async function ackAlert(alertId: string): Promise<void> {
  const res = await fetch(`${BASE}/alerts/${alertId}/ack`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export function listAlertRules(sessionId?: string): Promise<AlertRuleRecord[]> {
  return request("/alert-rules", { session_id: sessionId });
}

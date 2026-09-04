import { useEffect, useState } from "react";
import { ackAlert, listAlerts, listSessions } from "../api/client";
import type { AlertRecordOut, AlertStatus, SessionSummary } from "../types";

const STATUS_OPTIONS: (AlertStatus | "all")[] = ["open", "acknowledged", "resolved", "all"];

function statusBadgeClass(status: AlertStatus): string {
  if (status === "open") return "badge badge-critical";
  if (status === "acknowledged") return "badge badge-warning";
  return "badge badge-good";
}

export default function Alerts() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionFilter, setSessionFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "all">("open");
  const [alerts, setAlerts] = useState<AlertRecordOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  const load = () => {
    listAlerts(sessionFilter || undefined, statusFilter === "all" ? undefined : statusFilter)
      .then(setAlerts)
      .catch((e: Error) => setError(e.message));
  };

  useEffect(load, [sessionFilter, statusFilter]);

  const sessionName = (id: string) =>
    sessions.find((s) => s.session_id === id)?.model_name ?? id;

  const handleAck = async (alertId: string) => {
    await ackAlert(alertId);
    load();
  };

  return (
    <div className="page">
      <h1>Alerts</h1>
      <p className="subtitle">Threshold breaches across all monitored sessions.</p>

      <div className="filter-row">
        <select value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)}>
          <option value="">All sessions</option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.model_name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as AlertStatus | "all")}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="empty-state">Couldn&rsquo;t load alerts: {error}</div>}
      {!error && alerts === null && <div className="loading-state">Loading…</div>}
      {alerts !== null && alerts.length === 0 && (
        <div className="empty-state">No alerts match these filters.</div>
      )}

      {alerts !== null && alerts.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>Metric</th>
              <th>Observed</th>
              <th>Threshold</th>
              <th>Triggered</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.alert_id}>
                <td>{sessionName(a.session_id)}</td>
                <td>{a.metric_name}</td>
                <td>{a.observed_value.toFixed(4)}</td>
                <td>{a.threshold.toFixed(4)}</td>
                <td>{new Date(a.triggered_at).toLocaleString()}</td>
                <td>
                  <span className={statusBadgeClass(a.status)}>{a.status}</span>
                </td>
                <td>
                  {a.status === "open" && (
                    <button type="button" className="ack-button" onClick={() => handleAck(a.alert_id)}>
                      Acknowledge
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

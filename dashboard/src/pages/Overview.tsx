import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listSessions } from "../api/client";
import StatTile from "../components/layout/StatTile";
import type { SessionSummary } from "../types";

export default function Overview() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="page">
      <h1>Monitored models</h1>
      <p className="subtitle">Every session logged against this tracking URI.</p>

      {error && <div className="empty-state">Couldn&rsquo;t load sessions: {error}</div>}
      {!error && sessions === null && <div className="loading-state">Loading…</div>}
      {sessions !== null && sessions.length === 0 && (
        <div className="empty-state">
          No sessions yet. Call <code>driftwatch.init(...)</code> from your inference code to
          start one.
        </div>
      )}

      {sessions !== null && sessions.length > 0 && (
        <div className="session-grid">
          {sessions.map((s) => (
            <Link key={s.session_id} to={`/sessions/${s.session_id}`} className="card session-card">
              <div>
                <div className="session-name">{s.model_name}</div>
                <div className="session-meta">
                  {s.modality} · {s.status}
                </div>
              </div>
              <div className="stat-row">
                <StatTile label="Events" value={s.event_count} />
                <StatTile
                  label="Open alerts"
                  value={
                    <span className={s.open_alert_count > 0 ? "badge badge-critical" : ""}>
                      {s.open_alert_count}
                    </span>
                  }
                />
              </div>
              <div className="session-meta">
                {s.last_event_at
                  ? `Last event ${new Date(s.last_event_at).toLocaleString()}`
                  : "No events yet"}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

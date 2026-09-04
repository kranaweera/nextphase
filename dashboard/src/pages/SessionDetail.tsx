import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getBaseline, getMetrics, getSession } from "../api/client";
import MetricGroup from "../components/charts/MetricGroup";
import StatTile from "../components/layout/StatTile";
import type { Baseline, MetricCategory, MetricPoint, SessionDetailRecord } from "../types";

const TABS: { key: MetricCategory; label: string }[] = [
  { key: "drift", label: "Drift" },
  { key: "quality", label: "Quality" },
  { key: "performance", label: "Performance" },
];

export default function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<SessionDetailRecord | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [tab, setTab] = useState<MetricCategory>("drift");
  const [metrics, setMetrics] = useState<MetricPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    getSession(sessionId)
      .then(setSession)
      .catch((e: Error) => setError(e.message));
    getBaseline(sessionId)
      .then(setBaseline)
      .catch(() => setBaseline(null)); // no baseline logged yet
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    setMetrics(null);
    getMetrics(sessionId, tab)
      .then(setMetrics)
      .catch((e: Error) => setError(e.message));
  }, [sessionId, tab]);

  if (error) return <div className="page empty-state">Couldn&rsquo;t load session: {error}</div>;
  if (!session) return <div className="page loading-state">Loading…</div>;

  return (
    <div className="page">
      <Link to="/" className="session-meta">
        &larr; All sessions
      </Link>
      <h1>{session.model_name}</h1>
      <p className="subtitle">
        {session.modality} · created {new Date(session.created_at).toLocaleString()}
      </p>

      {baseline && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="stat-row">
            <StatTile label="Baseline rows" value={baseline.row_count} />
            <StatTile label="Features" value={Object.keys(baseline.column_schema).length} />
            <StatTile
              label="Baseline logged"
              value={new Date(baseline.created_at).toLocaleDateString()}
            />
          </div>
        </div>
      )}
      {!baseline && (
        <div className="empty-state" style={{ marginBottom: 20 }}>
          No baseline logged yet — call <code>session.log_baseline(...)</code> to enable drift
          detection.
        </div>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tab-button ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {metrics === null ? (
        <div className="loading-state">Loading metrics…</div>
      ) : (
        <MetricGroup points={metrics} />
      )}
    </div>
  );
}

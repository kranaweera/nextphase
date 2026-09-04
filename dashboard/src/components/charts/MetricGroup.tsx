import type { MetricPoint } from "../../types";
import TimeSeriesChart from "./TimeSeriesChart";

interface MetricGroupProps {
  points: MetricPoint[];
}

export default function MetricGroup({ points }: MetricGroupProps) {
  if (points.length === 0) {
    return (
      <div className="empty-state">
        No metrics computed yet for this window range. Metrics compute on a schedule once a
        time window has fully elapsed.
      </div>
    );
  }

  const byMetricName = new Map<string, MetricPoint[]>();
  for (const p of points) {
    const bucket = byMetricName.get(p.metric_name) ?? [];
    bucket.push(p);
    byMetricName.set(p.metric_name, bucket);
  }

  return (
    <div className="chart-grid">
      {Array.from(byMetricName.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([metricName, metricPoints]) => (
          <TimeSeriesChart key={metricName} title={metricName} points={metricPoints} />
        ))}
    </div>
  );
}

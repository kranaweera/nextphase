import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricPoint } from "../../types";

const SERIES_COLORS = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
];
const MAX_SERIES = 6;
const SINGLE_SERIES_KEY = "value";

function formatTick(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });
}

function pivotByFeature(points: MetricPoint[]): {
  rows: Record<string, number | string>[];
  seriesKeys: string[];
  omittedCount: number;
} {
  const seriesKeySet = new Set<string>();
  const rowsByWindow = new Map<string, Record<string, number | string>>();
  for (const p of points) {
    const key = p.feature_name ?? SINGLE_SERIES_KEY;
    seriesKeySet.add(key);
    const row = rowsByWindow.get(p.window_start) ?? { window_start: p.window_start };
    row[key] = p.value;
    rowsByWindow.set(p.window_start, row);
  }
  const rows = Array.from(rowsByWindow.values()).sort((a, b) =>
    String(a.window_start).localeCompare(String(b.window_start)),
  );
  const allKeys = Array.from(seriesKeySet).sort();
  const seriesKeys = allKeys.slice(0, MAX_SERIES);
  return { rows, seriesKeys, omittedCount: Math.max(0, allKeys.length - MAX_SERIES) };
}

interface TimeSeriesChartProps {
  title: string;
  points: MetricPoint[];
}

export default function TimeSeriesChart({ title, points }: TimeSeriesChartProps) {
  const { rows, seriesKeys, omittedCount } = pivotByFeature(points);
  const showLegend = seriesKeys.length > 1;

  return (
    <div className="chart-card card">
      <h3>{title.replace(/_/g, " ")}</h3>
      {omittedCount > 0 && (
        <span className="chart-note">
          +{omittedCount} more feature{omittedCount === 1 ? "" : "s"} not shown
        </span>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <XAxis
            dataKey="window_start"
            tickFormatter={formatTick}
            stroke="var(--baseline-axis)"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            minTickGap={24}
          />
          <YAxis
            stroke="var(--baseline-axis)"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            width={48}
          />
          <Tooltip
            labelFormatter={(label) => new Date(String(label)).toLocaleString()}
            contentStyle={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          {showLegend && <Legend wrapperStyle={{ fontSize: 11 }} />}
          {seriesKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={key === SINGLE_SERIES_KEY ? title.replace(/_/g, " ") : key}
              stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

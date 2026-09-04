export type Modality = "tabular" | "text" | "image";
export type MetricCategory = "drift" | "quality" | "performance";
export type AlertStatus = "open" | "acknowledged" | "resolved";
export type Comparator = ">" | ">=" | "<" | "<=" | "==";

export interface SessionSummary {
  session_id: string;
  model_name: string;
  modality: Modality;
  created_at: string;
  tracking_uri: string;
  metadata: Record<string, unknown>;
  status: string;
  event_count: number;
  last_event_at: string | null;
  open_alert_count: number;
}

export interface SessionDetailRecord {
  session_id: string;
  model_name: string;
  modality: Modality;
  created_at: string;
  tracking_uri: string;
  metadata: Record<string, unknown>;
  status: string;
}

export interface Baseline {
  baseline_id: string;
  session_id: string;
  created_at: string;
  row_count: number;
  column_schema: Record<string, unknown>;
  summary_stats: Record<string, unknown>;
}

export interface EventRecordOut {
  event_id: string;
  request_id: string;
  timestamp: string;
  status: string;
  latency_ms: number | null;
  input: unknown;
  output: unknown;
}

export interface MetricPoint {
  session_id: string;
  metric_category: MetricCategory;
  metric_name: string;
  feature_name: string | null;
  window_start: string;
  window_end: string;
  value: number;
  details: Record<string, unknown> | null;
  computed_at: string | null;
}

export interface AlertRuleRecord {
  rule_id: string;
  session_id: string;
  metric_name: string;
  feature_name: string | null;
  comparator: Comparator;
  threshold: number;
  window: string;
  consecutive_windows: number;
  enabled: boolean;
  notifiers: Record<string, unknown>[];
  created_at: string | null;
}

export interface AlertRecordOut {
  alert_id: string;
  rule_id: string;
  session_id: string;
  triggered_at: string;
  metric_name: string;
  observed_value: number;
  threshold: number;
  status: AlertStatus;
  details: Record<string, unknown> | null;
}

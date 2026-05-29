// -- Generic Timeseries (preparation for Investigation View) --

export interface TimeseriesPoint {
  timestamp: string;
  metric: string;
  value: number;
  source: string;
  device_id: string;
}

// -- API Response Types --

export interface Device {
  id: string;
  name: string;
  device_type: string;
  address: string;
  zone: string;
  status: string;
  last_seen: string;
}

export interface StatusResponse {
  devices: Device[];
}

export interface SensorReading {
  id: string;
  device_id: string;
  timestamp: string;
  metric: string;
  value: number;
}

export interface ReadingsResponse {
  readings: SensorReading[];
}

export interface Alert {
  id: string;
  timestamp: string;
  tier: 'info' | 'warning' | 'critical';
  source: string;
  message: string;
  resolved_at: string | null;
}

export interface AlertsResponse {
  alerts: Alert[];
}

export interface LightSchedule {
  id: string;
  device_id: string;
  date: string;
  on_time: string;
  off_time: string;
  pushed_at: string | null;
  recipe_snapshot: Record<string, unknown>;
}

export interface SchedulesResponse {
  schedules: LightSchedule[];
}

export interface AuthResponse {
  verified: boolean;
}

export interface PollingResponse {
  loops: Record<string, unknown>;
}

// -- SSE --

export type SSEEventType = 'sensor_update' | 'device_status' | 'irrigation' | 'schedule_pushed';

export interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

// -- Grow Composer Types --

export interface ChannelRuleWindow {
  start: string;
  duration_min: number;
}

export interface ChannelRule {
  rule: 'before_on' | 'after_off' | 'window';
  offset_min?: number;
  duration_min?: number;
  windows?: ChannelRuleWindow[];
}

export interface DimmingConfig {
  sunrise_min: number;
  sunset_min: number;
  max_pct: number;
  min_pct: number;
}

export interface RecipeData {
  name: string;
  photoperiod: { on: string; off: string };
  dimming: DimmingConfig;
  channels: Record<string, ChannelRule>;
}

export interface RecipeSummary {
  name: string;
  photoperiod: string;
  channels: number;
}

export interface RecipesResponse {
  recipes: RecipeSummary[];
}

export interface QueueEntry {
  recipe?: string;
  until?: string;
  transition_to?: string;
  days?: number;
}

export interface QueueResponse {
  entries: QueueEntry[];
}

export interface DeviceGroup {
  id: string;
  name: string;
  category: 'light' | 'irrigation' | 'climate' | 'other';
  device_ids: string[];
  color: string;
}

export interface GroupsResponse {
  groups: DeviceGroup[];
}

export interface DimmingPoint {
  time: number;
  pct: number;
}

export interface ChannelSchedule {
  channel: string;
  on_time: number;
  off_time: number;
}

export interface DayPlanResponse {
  date: string;
  recipe_name: string;
  transition_progress: number | null;
  main_on: number;
  main_off: number;
  dimming_curve: DimmingPoint[];
  channels: ChannelSchedule[];
}

// -- Helpers --

/** Convert a SensorReading to a generic TimeseriesPoint. */
export function toTimeseries(r: SensorReading, source: string): TimeseriesPoint {
  return {
    timestamp: r.timestamp,
    metric: r.metric,
    value: r.value,
    source,
    device_id: r.device_id
  };
}

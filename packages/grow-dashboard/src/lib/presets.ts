import type { ChannelRule, SensorTrigger } from "./types.js";

// ── Preset metadata ──

export interface PresetInfo {
  id: string;
  label: string;
  description: string;
  category: "light" | "irrigation" | "climate";
}

export const PRESETS: PresetInfo[] = [
  { id: "eod_far_red", label: "EOD Far-Red", description: "15min far-red after lights off", category: "light" },
  { id: "dawn_dusk", label: "Dawn/Dusk Ramp", description: "5-channel spectral transition", category: "light" },
  { id: "veg_steering", label: "Veg Steering", description: "Frequent irrigation, low dry-back", category: "irrigation" },
  { id: "gen_steering", label: "Gen Steering", description: "Aggressive dry-back for generative", category: "irrigation" },
  { id: "four_phase", label: "4-Phase Irrigation", description: "Pre-Dawn/Ramp/Maintain/Taper", category: "irrigation" },
];

// ── Light presets ──

export function eodFarRedChannel(): Record<string, ChannelRule> {
  return { far_red: { rule: "after_off", offset_min: 0, duration_min: 15 } };
}

export function dawnDuskChannels(): Record<string, ChannelRule> {
  return {
    deep_blue: { rule: "before_on", offset_min: 30, duration_min: 30 },
    dawn: { rule: "before_on", offset_min: 15, duration_min: 15 },
    far_red: { rule: "after_off", offset_min: 0, duration_min: 15 },
    uva: { rule: "window", windows: [{ start: "11:00", duration_min: 30 }] },
  };
}

// ── Crop steering presets ──

export function vegSteeringTriggers(targetGroup: string): SensorTrigger[] {
  return [
    { sensorType: "soil_moisture", operator: "lt", threshold: 40, targetGroup, action: "on" },
    { sensorType: "soil_moisture", operator: "gt", threshold: 55, targetGroup, action: "off" },
  ];
}

export function genSteeringTriggers(targetGroup: string): SensorTrigger[] {
  return [
    { sensorType: "soil_moisture", operator: "lt", threshold: 25, targetGroup, action: "on" },
    { sensorType: "soil_moisture", operator: "gt", threshold: 35, targetGroup, action: "off" },
  ];
}

// ── 4-Phase irrigation ──

function parseTime(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

function fmtTime(mins: number): string {
  const m = ((mins % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export function fourPhaseIrrigation(
  onTime: string,
  offTime: string,
  targetGroup: string,
): { channels: Record<string, ChannelRule>; triggers: SensorTrigger[] } {
  const on = parseTime(onTime);
  const off = parseTime(offTime);

  // P1: Ramp-Up Window — starts 30min after main_on, duration 60min
  const p1Start = fmtTime(on + 30);
  // P3: Taper Window — starts 120min before main_off, duration 30min
  const p3Start = fmtTime(off - 120);

  const channels: Record<string, ChannelRule> = {
    irrigation_ramp: { rule: "window", windows: [{ start: p1Start, duration_min: 60 }] },
    irrigation_taper: { rule: "window", windows: [{ start: p3Start, duration_min: 30 }] },
  };

  const triggers: SensorTrigger[] = [
    { sensorType: "soil_moisture", operator: "lt", threshold: 30, targetGroup, action: "on" },
    { sensorType: "soil_moisture", operator: "gt", threshold: 60, targetGroup, action: "off" },
  ];

  return { channels, triggers };
}

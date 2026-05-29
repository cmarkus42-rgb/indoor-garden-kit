import type { Device } from '$lib/types.js';

export function visibleDevices(devices: Device[], view: string): Device[] {
  return devices.filter(d => d.enabled !== false && d.view_visibility?.[view] !== false);
}

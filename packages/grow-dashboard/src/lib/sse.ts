import { writable, readonly } from 'svelte/store';
import type { SSEEvent, SSEEventType } from './types.js';

const _events = writable<SSEEvent | null>(null);
const _connected = writable(false);

export const sseLatest = readonly(_events);
export const sseConnected = readonly(_connected);

let source: EventSource | null = null;
let retryMs = 1000;
const MAX_RETRY = 30000;

const EVENT_TYPES: SSEEventType[] = [
  'sensor_update',
  'device_status',
  'irrigation',
  'schedule_pushed'
];

function connect() {
  if (source) {
    source.close();
  }
  source = new EventSource('/api/events');

  source.onopen = () => {
    _connected.set(true);
    retryMs = 1000;
  };

  source.onerror = () => {
    _connected.set(false);
    source?.close();
    source = null;
    setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 2, MAX_RETRY);
  };

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        _events.set({ type, data });
      } catch {
        // skip malformed events
      }
    });
  }
}

export function sseStart() {
  if (!source) connect();
}

export function sseStop() {
  source?.close();
  source = null;
  _connected.set(false);
}

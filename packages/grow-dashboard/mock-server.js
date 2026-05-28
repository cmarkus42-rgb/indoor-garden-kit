import { createServer } from 'node:http';

// ── Mock Devices ──

const devices = [
  { id: 'plug-01', name: 'Plug Main Light', device_type: 'shelly_plug', address: '192.168.x.1', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'plug-02', name: 'Plug Far-Red', device_type: 'shelly_plug', address: '192.168.x.2', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'plug-03', name: 'Plug Dawn', device_type: 'shelly_plug', address: '192.168.x.3', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'plug-04', name: 'Plug Exhaust Fan', device_type: 'shelly_plug', address: '192.168.x.4', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'plug-05', name: 'Plug Circulation Fan', device_type: 'shelly_plug', address: '192.168.x.5', zone: 'tent-b', status: 'offline', last_seen: new Date(Date.now() - 3600000).toISOString() },
  { id: 'relay-01', name: 'Relay Irrigation Zone A', device_type: 'shelly_relay', address: '192.168.x.10', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'relay-02', name: 'Relay Irrigation Zone B', device_type: 'shelly_relay', address: '192.168.x.11', zone: 'tent-b', status: 'online', last_seen: new Date().toISOString() },
  { id: 'blu-01', name: 'BLU Canopy Left', device_type: 'blu_ht', address: 'fc:4d:6a:xx:01', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'blu-02', name: 'BLU Canopy Right', device_type: 'blu_ht', address: 'fc:4d:6a:xx:02', zone: 'tent-a', status: 'online', last_seen: new Date().toISOString() },
  { id: 'blu-03', name: 'BLU Floor Level', device_type: 'blu_ht', address: 'c0:2c:ed:xx:03', zone: 'tent-b', status: 'online', last_seen: new Date().toISOString() },
  { id: 'eco-indoor', name: 'Ecowitt Indoor', device_type: 'ecowitt_indoor', address: '192.168.x.20', zone: 'room', status: 'online', last_seen: new Date().toISOString() },
  ...Array.from({ length: 8 }, (_, i) => ({
    id: `soil-0${i + 1}`,
    name: `Soil Channel ${i + 1}`,
    device_type: 'ecowitt_sensor',
    address: `ch${i + 1}`,
    zone: i < 4 ? 'tent-a' : 'tent-b',
    status: 'online',
    last_seen: new Date().toISOString()
  }))
];

// ── Mock Readings Generator ──

function generateReadings(deviceId, metrics, count = 20) {
  const readings = [];
  const now = Date.now();
  for (let i = 0; i < count; i++) {
    for (const [metric, gen] of Object.entries(metrics)) {
      readings.push({
        id: `${deviceId}-${metric}-${i}`,
        device_id: deviceId,
        timestamp: new Date(now - i * 30000).toISOString(),
        metric,
        value: gen(i)
      });
    }
  }
  return readings;
}

const readingsMap = {
  'blu-01': () => generateReadings('blu-01', {
    temperature: (i) => +(26.5 + Math.sin(i * 0.3) * 1.5).toFixed(1),
    humidity: (i) => +(62 + Math.sin(i * 0.2) * 8).toFixed(1),
    vpd: (i) => +(1.05 + Math.sin(i * 0.3) * 0.2).toFixed(2),
    battery: () => 100,
    rssi: (i) => -45 - Math.floor(Math.random() * 10)
  }),
  'blu-02': () => generateReadings('blu-02', {
    temperature: (i) => +(27.0 + Math.sin(i * 0.25) * 1.2).toFixed(1),
    humidity: (i) => +(58 + Math.sin(i * 0.2) * 6).toFixed(1),
    vpd: (i) => +(1.15 + Math.sin(i * 0.25) * 0.15).toFixed(2),
    battery: () => 98,
    rssi: (i) => -50 - Math.floor(Math.random() * 8)
  }),
  'blu-03': () => generateReadings('blu-03', {
    temperature: (i) => +(24.0 + Math.sin(i * 0.2) * 2.0).toFixed(1),
    humidity: (i) => +(68 + Math.sin(i * 0.15) * 5).toFixed(1),
    vpd: (i) => +(0.85 + Math.sin(i * 0.2) * 0.18).toFixed(2),
    battery: () => 95,
    rssi: (i) => -55 - Math.floor(Math.random() * 12)
  }),
  'eco-indoor': () => generateReadings('eco-indoor', {
    temperature: (i) => +(23.5 + Math.sin(i * 0.1) * 1.0).toFixed(1),
    humidity: (i) => +(45 + Math.sin(i * 0.15) * 5).toFixed(1),
    pressure: (i) => +(1013 + Math.sin(i * 0.05) * 2).toFixed(1)
  }),
  ...Object.fromEntries(Array.from({ length: 8 }, (_, i) => [
    `soil-0${i + 1}`,
    () => generateReadings(`soil-0${i + 1}`, {
      soil_moisture: (j) => +(20 + i * 5 + Math.sin(j * 0.3) * 8).toFixed(0),
      battery: () => [1.4, 1.4, 1.4, 1.5, 1.4, 1.5, 1.4, 1.6][i]
    }, 5)
  ])),
  ...Object.fromEntries(['plug-01', 'plug-02', 'plug-03', 'plug-04', 'plug-05'].map(id => [
    id,
    () => generateReadings(id, {
      power: (i) => +(id === 'plug-01' ? 240 + Math.sin(i * 0.5) * 10 : 45 + Math.random() * 15).toFixed(1),
      energy: (i) => +(5.2 + i * 0.01).toFixed(3),
      temperature: (i) => +(38 + Math.sin(i * 0.2) * 3).toFixed(1)
    })
  ]))
};

// ── Mock Schedules ──

const schedules = [
  { id: 'sch-01', device_id: 'plug-01', date: '2026-05-27', on_time: '06:00', off_time: '00:00', pushed_at: new Date().toISOString(), recipe_snapshot: { phase: 'veg', light_type: 'main', photoperiod: '18/6' } },
  { id: 'sch-02', device_id: 'plug-02', date: '2026-05-27', on_time: '00:00', off_time: '00:15', pushed_at: new Date().toISOString(), recipe_snapshot: { phase: 'veg', light_type: 'far_red', offset_after_min: 15 } },
  { id: 'sch-03', device_id: 'plug-03', date: '2026-05-27', on_time: '05:30', off_time: '06:00', pushed_at: null, recipe_snapshot: { phase: 'veg', light_type: 'dawn', offset_before_min: 30 } },
];

// ── Mock Alerts ──

const alerts = [
  { id: 'a-01', timestamp: new Date(Date.now() - 120000).toISOString(), tier: 'critical', source: 'health_check', message: 'Device plug-05 went offline — no response for 300s', resolved_at: null },
  { id: 'a-02', timestamp: new Date(Date.now() - 600000).toISOString(), tier: 'warning', source: 'irrigation', message: 'Zone B soil moisture below 15% — irrigation triggered', resolved_at: new Date(Date.now() - 300000).toISOString() },
  { id: 'a-03', timestamp: new Date(Date.now() - 1800000).toISOString(), tier: 'info', source: 'schedule_push', message: 'Pushed 3 schedules to devices', resolved_at: new Date(Date.now() - 1800000).toISOString() },
  { id: 'a-04', timestamp: new Date(Date.now() - 3600000).toISOString(), tier: 'warning', source: 'vpd', message: 'VPD at BLU Floor Level dropped to 0.65 kPa — below veg optimum', resolved_at: null },
  { id: 'a-05', timestamp: new Date(Date.now() - 7200000).toISOString(), tier: 'info', source: 'openclaw', message: 'Adjusted irrigation threshold for Zone A from 25% to 30%', resolved_at: new Date(Date.now() - 7200000).toISOString() },
  { id: 'a-06', timestamp: new Date(Date.now() - 14400000).toISOString(), tier: 'critical', source: 'shelly_rpc', message: 'RPC timeout on relay-02 — 3 consecutive failures', resolved_at: new Date(Date.now() - 10800000).toISOString() },
];

// ── Mock Polling Status ──

const pollingStatus = {
  loops: {
    shelly_poll: { running: true, interval_s: 30, run_count: 482, last_run: new Date().toISOString(), last_error: null },
    ecowitt_ingest: { running: true, interval_s: 30, run_count: 481, last_run: new Date().toISOString(), last_error: null },
    blu_poll: { running: true, interval_s: 30, run_count: 480, last_run: new Date().toISOString(), last_error: null },
    health_check: { running: true, interval_s: 60, run_count: 241, last_run: new Date().toISOString(), last_error: null },
    irrigation_eval: { running: true, interval_s: 30, run_count: 482, last_run: new Date().toISOString(), last_error: null },
    schedule_push: { running: true, interval_s: 300, run_count: 29, last_run: new Date().toISOString(), last_error: null },
  }
};

// ── SSE ──

const sseClients = new Set();

function broadcastSSE(event, data) {
  const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of sseClients) {
    res.write(msg);
  }
}

// Simulate live updates every 10s
setInterval(() => {
  broadcastSSE('sensor_update', { source: 'blu_ht', timestamp: new Date().toISOString(), channels: ['blu-01', 'blu-02', 'blu-03'] });
}, 10000);

setInterval(() => {
  broadcastSSE('sensor_update', { source: 'shelly', timestamp: new Date().toISOString(), channels: ['plug-01', 'plug-02'] });
}, 15000);

setInterval(() => {
  broadcastSSE('sensor_update', { source: 'ecowitt', timestamp: new Date().toISOString(), channels: ['soil-01', 'soil-02', 'soil-03'] });
}, 20000);

// ── Mock Recipes ──

const recipes = {
  'Veg Standard': {
    name: 'Veg Standard',
    photoperiod: { on: '06:00', off: '00:00' },
    dimming: { sunrise_min: 30, sunset_min: 30, max_pct: 100, min_pct: 0 },
    channels: {
      far_red: { rule: 'after_off', offset_min: 1, duration_min: 15 },
      dawn: { rule: 'before_on', offset_min: 30 },
      deep_blue: { rule: 'before_on', offset_min: 15 },
      uva: { rule: 'window', windows: [
        { start: '11:00', duration_min: 30 },
        { start: '14:00', duration_min: 30 }
      ]}
    }
  },
  'Flower Standard': {
    name: 'Flower Standard',
    photoperiod: { on: '08:00', off: '20:00' },
    dimming: { sunrise_min: 45, sunset_min: 45, max_pct: 100, min_pct: 0 },
    channels: {
      far_red: { rule: 'after_off', offset_min: 1, duration_min: 15 },
      dawn: { rule: 'before_on', offset_min: 20 },
      uva: { rule: 'window', windows: [
        { start: '12:00', duration_min: 30 }
      ]}
    }
  },
  'Transition Soft Flip': {
    name: 'Transition Soft Flip',
    photoperiod: { on: '07:00', off: '22:00' },
    dimming: { sunrise_min: 35, sunset_min: 35, max_pct: 90, min_pct: 0 },
    channels: {
      far_red: { rule: 'after_off', offset_min: 1, duration_min: 15 },
      dawn: { rule: 'before_on', offset_min: 25 },
      deep_blue: { rule: 'before_on', offset_min: 10 }
    }
  }
};

let recipeQueue = [
  { recipe: 'Veg Standard', until: '2026-06-01' },
  { transition_to: 'Flower Standard', days: 7 },
  { recipe: 'Flower Standard' }
];

// ── HTTP Server ──

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;

  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

  // SSE
  if (path === '/api/events') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive' });
    res.write(': keepalive\n\n');
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }

  // JSON helper
  const json = (data, status = 200) => {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  };

  // ── Recipe Store (in-memory) ──

  const readBody = (req) => new Promise((resolve) => {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch { resolve(null); } });
  });

  // Routes
  if (path === '/health') return json({ status: 'ok', subscribers: sseClients.size });
  if (path === '/api/status') return json({ devices });
  if (path === '/api/alerts') return json({ alerts });
  if (path === '/api/schedules') return json({ schedules });
  if (path === '/api/polling') return json(pollingStatus);

  if (path.startsWith('/api/readings/')) {
    const deviceId = path.split('/').pop();
    const limit = parseInt(url.searchParams.get('limit') || '20');
    const gen = readingsMap[deviceId];
    return json({ readings: gen ? gen().slice(0, limit) : [] });
  }

  if (path === '/api/auth/verify' && req.method === 'POST') {
    const body = await readBody(req);
    return json({ verified: body?.pin === '1234' });
  }

  // ── Recipe Endpoints ──

  if (path === '/api/recipes' && req.method === 'GET') {
    return json({
      recipes: Object.values(recipes).map(r => ({
        name: r.name,
        photoperiod: `${r.photoperiod.on}-${r.photoperiod.off}`,
        channels: Object.keys(r.channels || {}).length
      }))
    });
  }

  if (path.startsWith('/api/recipes/') && req.method === 'GET') {
    const name = decodeURIComponent(path.split('/').pop());
    if (recipes[name]) return json(recipes[name]);
    return json({ error: 'not found' }, 404);
  }

  if (path.startsWith('/api/recipes/') && req.method === 'PUT') {
    const body = await readBody(req);
    if (body && body.name) {
      recipes[body.name] = body;
      return json({ status: 'saved', name: body.name });
    }
    return json({ error: 'invalid recipe' }, 422);
  }

  if (path.startsWith('/api/recipes/') && req.method === 'DELETE') {
    const name = decodeURIComponent(path.split('/').pop());
    if (recipes[name]) {
      delete recipes[name];
      return json({ status: 'deleted' });
    }
    return json({ error: 'not found' }, 404);
  }

  // ── Queue Endpoints ──

  if (path === '/api/queue' && req.method === 'GET') {
    return json({ queue: recipeQueue, active_recipe: recipeQueue[0]?.recipe || null, transition_progress: null });
  }

  if (path === '/api/queue' && req.method === 'PUT') {
    const body = await readBody(req);
    if (body && Array.isArray(body)) {
      recipeQueue.splice(0, recipeQueue.length, ...body);
      return json({ status: 'updated' });
    }
    return json({ error: 'invalid queue' }, 422);
  }

  // ── Schedule/Today ──

  if (path === '/api/schedule/today') {
    const active = recipes['Veg Standard'] || Object.values(recipes)[0];
    if (!active) return json({ error: 'no active recipe' }, 404);
    const [onH, onM] = active.photoperiod.on.split(':').map(Number);
    const [offH, offM] = active.photoperiod.off.split(':').map(Number);
    const mainOn = onH * 60 + onM;
    const mainOff = offH * 60 + offM;
    const sr = active.dimming?.sunrise_min || 30;
    const ss = active.dimming?.sunset_min || 30;
    const maxPct = active.dimming?.max_pct ?? 100;
    const minPct = active.dimming?.min_pct ?? 0;

    const channelSchedules = [];
    for (const [ch, rule] of Object.entries(active.channels || {})) {
      if (rule.rule === 'before_on') {
        channelSchedules.push({ channel: ch, on_time: mainOn - (rule.offset_min || 0), off_time: rule.duration_min ? mainOn - (rule.offset_min || 0) + rule.duration_min : mainOn });
      } else if (rule.rule === 'after_off') {
        const on = mainOff + (rule.offset_min || 0);
        channelSchedules.push({ channel: ch, on_time: on, off_time: on + (rule.duration_min || 15) });
      } else if (rule.rule === 'window' && rule.windows) {
        for (const w of rule.windows) {
          const [wH, wM] = w.start.split(':').map(Number);
          channelSchedules.push({ channel: ch, on_time: wH * 60 + wM, off_time: wH * 60 + wM + (w.duration_min || 30) });
        }
      }
    }

    return json({
      date: new Date().toISOString().split('T')[0],
      recipe_name: active.name,
      transition_progress: null,
      main_on: mainOn,
      main_off: mainOff,
      dimming_curve: [
        { time: mainOn, pct: minPct },
        { time: mainOn + sr, pct: maxPct },
        { time: mainOff - ss, pct: maxPct },
        { time: mainOff, pct: minPct }
      ],
      channels: channelSchedules
    });
  }

  json({ error: 'not found' }, 404);
});

const PORT = 8000;
server.listen(PORT, () => {
  console.log(`Mock API server running on http://localhost:${PORT}`);
  console.log('PIN: 1234');
  console.log('SSE events every 10-20s');
});

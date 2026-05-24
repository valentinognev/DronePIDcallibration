const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export interface Session {
  session_id: string;
  firmware: string;
}

export interface FileInfo {
  file_id: string;
  original_name: string;
  log_count: number;
  log_names: string[];
}

export interface TraceData {
  time_range: [number, number];
  full_time_range: [number, number];
  epoch: [number, number];
  lograte_khz: number;
  panels: Record<string, Array<{ key: string; label: string; color: string; x: number[]; y: number[] }>>;
  motor_panel: Array<{ key: string; label: string; color: string; x: number[]; y: number[]; yaxis?: 'y' | 'y2' }>;
  motor_panel_units?: { throttle: string; motors: string };
  available_traces: string[];
  metadata: Record<string, unknown>;
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  firmwares: () => request<Array<{ key: string; display_name: string }>>('/sessions/firmwares'),

  createSession: (firmware: string) =>
    request<Session>('/sessions', { method: 'POST', body: JSON.stringify({ firmware }) }),

  getSession: (id: string) =>
    request<{ session_id: string; firmware: string; files: FileInfo[] }>(`/sessions/${id}`),

  uploadFile: async (sessionId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/files`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<FileInfo>;
  },

  getTraces: (sessionId: string, body: Record<string, unknown>) =>
    request<TraceData>(`/sessions/${sessionId}/traces`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateEpoch: (sessionId: string, fileIdx: number, logIdx: number, start: number, end: number) =>
    request(`/sessions/${sessionId}/files/${fileIdx}/logs/${logIdx}/epoch`, {
      method: 'PATCH',
      body: JSON.stringify({ epoch_start: start, epoch_end: end }),
    }),

  getSetupInfo: (sessionId: string, fileIdx: number, logIdx: number) =>
    request(`/sessions/${sessionId}/files/${fileIdx}/logs/${logIdx}/setup`),

  runFilterSim: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/filter-sim', { method: 'POST', body: JSON.stringify(body) }),

  runStats: (body: Record<string, unknown>) =>
    request<{ stats: Record<string, unknown>; motor_noise: Record<string, { freq: number[]; psd: number[] }> }>(
      '/analysis/stats',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  runChirp: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/chirp', { method: 'POST', body: JSON.stringify(body) }),

  setupDiff: (body: Record<string, unknown>) =>
    request<{ file_a: string; file_b: string; rows: Array<{ line: number; key: string; value_a: string; value_b: string; diff: boolean }> }>(
      '/analysis/setup-diff',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  runSpectrum: (body: Record<string, unknown>) =>
    request<{ results: Array<Record<string, unknown>> }>('/analysis/spectrum', { method: 'POST', body: JSON.stringify(body) }),

  runStepResponse: (body: Record<string, unknown>) =>
    request<{ results: Array<Record<string, unknown>> }>('/analysis/step-response', { method: 'POST', body: JSON.stringify(body) }),

  runThrottleSpectrum: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/throttle-spectrum', { method: 'POST', body: JSON.stringify(body) }),

  runTimeFreq: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/time-freq', { method: 'POST', body: JSON.stringify(body) }),

  getSettings: () => request<Record<string, unknown>>('/settings'),
  saveSettings: (settings: Record<string, unknown>) =>
    request('/settings', { method: 'PUT', body: JSON.stringify(settings) }),
};

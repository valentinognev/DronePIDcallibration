const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    let message = err || res.statusText;
    try {
      const body = JSON.parse(err) as { detail?: unknown };
      if (typeof body.detail === 'string') {
        message = body.detail;
      }
    } catch {
      /* not JSON — use raw body */
    }
    throw new Error(message);
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
  parse_warnings?: string[];
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

export interface StepAxisStats {
  n: number;
  peak_mean?: number;
  peak_std?: number;
  latency_mean_ms?: number;
}

export interface StepAxisResult {
  time_ms: number[];
  curves: number[][];
  mean_curve: number[];
  stats: StepAxisStats;
  pidf?: string;
}

export interface StepResponseResult {
  file_idx: number;
  name: string;
  axes?: Record<'roll' | 'pitch' | 'yaw', StepAxisResult>;
  signals?: Record<string, Record<'roll' | 'pitch' | 'yaw', StepAxisResult>>;
}

export interface StepResponseRequest {
  session_id: string;
  file_indices: number[];
  log_idx?: number;
  axes?: number[];
  smooth_factor?: number;
  y_correction?: boolean;
  signals?: string[];
  epoch_start?: number[];
  epoch_end?: number[];
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
    if (!res.ok) {
      const err = await res.text();
      let message = err || res.statusText;
      try {
        const body = JSON.parse(err) as { detail?: unknown };
        if (typeof body.detail === 'string') {
          message = body.detail;
        }
      } catch {
        /* not JSON */
      }
      throw new Error(message);
    }
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

  runOverlayCapabilities: (body: {
    session_id: string;
    file_indices: number[];
    rpm_estimate?: boolean;
    rpm_multiplier?: number;
  }) =>
    request<{
      rpm_notch: { available: boolean; message: string };
      dyn_notch: { available: boolean; message: string };
    }>('/analysis/overlay-capabilities', { method: 'POST', body: JSON.stringify(body) }),

  runStepResponse: (body: StepResponseRequest) =>
    request<{ results: StepResponseResult[] }>('/analysis/step-response', { method: 'POST', body: JSON.stringify(body) }),

  runThrottleSpectrum: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/throttle-spectrum', { method: 'POST', body: JSON.stringify(body) }),

  runTimeFreq: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/analysis/time-freq', { method: 'POST', body: JSON.stringify(body) }),

  getSettings: () => request<Record<string, unknown>>('/settings'),

  saveSettings: (settings: Record<string, unknown>) =>
    request('/settings', { method: 'PUT', body: JSON.stringify(settings) }),

  sysIdCapabilities: (body: { session_id: string; file_idx?: number; log_idx?: number }) =>
    request<SysIdCapabilities>('/analysis/sysid/capabilities', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  sysIdDefaults: (body: { session_id: string; file_idx?: number; log_idx?: number }) =>
    request<SysIdDefaults>('/analysis/sysid/defaults', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  sysIdPreview: (body: SysIdPreviewRequest) =>
    request<SysIdPreviewResult>('/analysis/sysid/preview', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  sysIdRun: (body: SysIdRunRequest) =>
    request<SysIdRunResult>('/analysis/sysid/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

export interface SysIdModel {
  mass: number;
  gravity: number;
  inertia_ratio: number;
  rotor_positions: number[][];
  rotor_thrust_directions: number[][];
  rotor_torque_directions: number[][];
}

export interface SysIdTimeframe {
  file_idx: number;
  start: number;
  end: number;
}

export interface SysIdCapabilities {
  ready: boolean;
  missing: string[];
  motor_source: string | null;
  frame_convention: string;
  accel_unit: string;
}

export interface SysIdDefaults {
  mass: number | null;
  rotor_positions: number[][] | null;
  rotor_thrust_directions: number[][] | null;
  rotor_torque_directions: number[][] | null;
  frame_convention: string;
}

export interface SysIdPreviewFlight {
  name: string;
  motor_source?: string;
  frame_convention?: string;
  time_range: [number, number];
  metrics: {
    timestamps: number[];
    motors: Record<string, number[]>;
    thrust_z: { timestamps: number[]; values: number[] };
    torque_x: { timestamps: number[]; values: number[] };
    torque_y: { timestamps: number[]; values: number[] };
    torque_z: { timestamps: number[]; values: number[] };
  };
}

export interface SysIdPreviewResult {
  flights: SysIdPreviewFlight[];
}

export interface SysIdPreviewRequest {
  session_id: string;
  file_indices: number[];
  log_idx?: number;
  model: SysIdModel;
}

export interface SysIdRunRequest {
  session_id: string;
  file_indices: number[];
  log_idx?: number;
  model: SysIdModel;
  exponents?: number[];
  separate_motors?: boolean;
  timeframes_thrust: SysIdTimeframe[];
  timeframes_inertia_rp: SysIdTimeframe[];
  timeframes_inertia_yaw: SysIdTimeframe[];
  t_m_steps?: number;
  t_m_min?: number;
  t_m_max?: number;
}

export interface SysIdRunResult {
  parameters: {
    t_m: number;
    k_f: number[][];
    k_f_mean: number[];
    thrust_rmse: number;
    i_xx: number;
    i_yy: number;
    i_zz: number;
    k_tau: number;
    mass: number;
    inertia_ratio: number;
  };
  plots: Record<string, unknown>;
}

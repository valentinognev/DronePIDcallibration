export type AppTheme = 'dark' | 'light';

export const TRACE_LABELS: Record<string, string> = {
  gyro: 'Gyro',
  gyro_pf: 'Gyro(pf)',
  pterm: 'P-term',
  iterm: 'I-term',
  dterm_pf: 'D-term(pf)',
  dterm: 'D-term',
  fterm: 'F-term',
  setpoint: 'Set point',
  pidsum: 'PID sum',
  piderr: 'PID error',
  throttle: 'Throttle',
  motor_0: 'Motor 1',
  motor_1: 'Motor 2',
  motor_2: 'Motor 3',
  motor_3: 'Motor 4',
  debug: 'Debug',
  accel: 'Accel',
  attitude: 'Attitude',
  attitude_sp: 'Attitude SP',
  velocity: 'Velocity',
  velocity_sp: 'Velocity SP',
};

export const TRACE_COLORS: Record<string, string> = {
  gyro: '#ffffff',
  gyro_pf: '#999999',
  pterm: '#00b300',
  iterm: '#1a66cc',
  dterm_pf: '#ccb31a',
  dterm: '#ff9900',
  fterm: '#ff33cc',
  setpoint: '#ff0000',
  pidsum: '#9933cc',
  piderr: '#00cccc',
  throttle: '#ffffff',
  motor_0: '#e60000',
  motor_1: '#ff9900',
  motor_2: '#0099ff',
  motor_3: '#00cccc',
  debug: '#ff0000',
  accel: '#ff66cc',
  attitude: '#66ff66',
  attitude_sp: '#ff6666',
  velocity: '#66ccff',
  velocity_sp: '#ffcc66',
};

/** Betaflight / INAV default trace keys for Log Viewer. */
export const BETAFLIGHT_DEFAULT_TRACES = [
  'gyro', 'setpoint', 'pterm', 'iterm', 'dterm', 'dterm_pf', 'fterm',
  'pidsum', 'piderr', 'throttle', 'motor_0', 'motor_1', 'motor_2', 'motor_3',
] as const;

/** PX4-only trace keys (also included in DEFAULT_TRACES for toggle labels/colors). */
export const PX4_EXTRA_TRACES = [
  'accel', 'attitude', 'attitude_sp', 'velocity', 'velocity_sp',
] as const;

export const DEFAULT_TRACES = [...BETAFLIGHT_DEFAULT_TRACES, ...PX4_EXTRA_TRACES];

/** Sensible Log Viewer defaults when PX4 channels are available. */
export const PX4_DEFAULT_VISIBLE = [
  'gyro', 'setpoint', 'attitude', 'attitude_sp', 'velocity', 'velocity_sp', 'throttle',
] as const;

export const STEP_SIGNAL_MODES = [
  { key: 'rate', label: 'Rate' },
  { key: 'attitude', label: 'Attitude' },
  { key: 'velocity', label: 'Velocity' },
  { key: 'accel', label: 'Accel' },
] as const;

export type StepSignalMode = (typeof STEP_SIGNAL_MODES)[number]['key'];

const PLOT_LAYOUT_DARK = {
  paper_bgcolor: '#1a1a1a',
  plot_bgcolor: '#1a1a1a',
  font: { color: '#e5e5e5', size: 11 },
  margin: { l: 50, r: 20, t: 30, b: 40 },
  xaxis: { gridcolor: '#333', zerolinecolor: '#555' },
  yaxis: { gridcolor: '#333', zerolinecolor: '#555' },
};

const PLOT_LAYOUT_LIGHT = {
  paper_bgcolor: '#f5f5f5',
  plot_bgcolor: '#f5f5f5',
  font: { color: '#1a1a1a', size: 11 },
  margin: { l: 50, r: 20, t: 30, b: 40 },
  xaxis: { gridcolor: '#cccccc', zerolinecolor: '#999999' },
  yaxis: { gridcolor: '#cccccc', zerolinecolor: '#999999' },
};

/** @deprecated Prefer getPlotLayoutBase(theme) */
export const PLOT_LAYOUT_BASE = PLOT_LAYOUT_DARK;

export function getPlotLayoutBase(theme: AppTheme) {
  return theme === 'light' ? PLOT_LAYOUT_LIGHT : PLOT_LAYOUT_DARK;
}

const LIGHT_LINE_OVERRIDES: Record<string, string> = {
  '#ffffff': '#1a1a1a',
  '#999999': '#666666',
  '#ffff00': '#b8860b',
};

export function adaptPlotLineColor(color: string, theme: AppTheme): string {
  if (theme === 'dark') return color;
  return LIGHT_LINE_OVERRIDES[color.toLowerCase()] ?? color;
}

export function getTraceColor(key: string, theme: AppTheme): string {
  return adaptPlotLineColor(TRACE_COLORS[key] || '#ffffff', theme);
}

export const COLORMAPS = ['Hot', 'Jet', 'Viridis', 'Plasma', 'Electric'] as const;

/** Distinct colors for multi-file overlays (spectral, step response, etc.) */
export const FILE_OVERLAY_COLORS = [
  '#ff4444',
  '#44aaff',
  '#44dd44',
  '#ffaa00',
  '#cc44ff',
  '#00dddd',
  '#ff88cc',
  '#aaff44',
  '#8888ff',
  '#ff8844',
];

export const AXIS_LABELS = ['Roll', 'Pitch', 'Yaw'] as const;

export interface FirmwareOption {
  key: string;
  display_name: string;
}

/** Fallback when GET /sessions/firmwares is unavailable. */
export const FALLBACK_FIRMWARES: FirmwareOption[] = [
  { key: 'betaflight', display_name: 'Betaflight' },
  { key: 'emuflight', display_name: 'Emuflight' },
  { key: 'inav', display_name: 'INAV' },
  { key: 'fettec', display_name: 'FETTEC' },
  { key: 'quicksilver', display_name: 'QuickSilver' },
  { key: 'rotorflight', display_name: 'Rotorflight' },
  { key: 'kiss', display_name: 'KISS Ultra' },
  { key: 'ardupilot', display_name: 'ArduPilot' },
  { key: 'px4', display_name: 'PX4' },
];

export const LOG_FILE_ACCEPT = '.bbl,.bfl,.csv,.bin,.json,.txt,.ulg';

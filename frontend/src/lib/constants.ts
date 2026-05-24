export type AppTheme = 'dark' | 'light';

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
};

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

export const AXIS_LABELS = ['Roll', 'Pitch', 'Yaw'] as const;

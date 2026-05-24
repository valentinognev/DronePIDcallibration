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

export const PLOT_LAYOUT_BASE = {
  paper_bgcolor: '#1a1a1a',
  plot_bgcolor: '#1a1a1a',
  font: { color: '#e5e5e5', size: 11 },
  margin: { l: 50, r: 20, t: 30, b: 40 },
  xaxis: { gridcolor: '#333', zerolinecolor: '#555' },
  yaxis: { gridcolor: '#333', zerolinecolor: '#555' },
};

export const COLORMAPS = ['Hot', 'Jet', 'Viridis', 'Plasma', 'Electric'] as const;

export const AXIS_LABELS = ['Roll', 'Pitch', 'Yaw'] as const;

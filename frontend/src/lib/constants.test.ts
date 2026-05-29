import { describe, expect, it } from 'vitest';
import {
  TRACE_COLORS,
  adaptPlotLineColor,
  getPlotLayoutBase,
  tracePanelTitle,
} from '../lib/constants';

describe('constants', () => {
  it('has trace colors defined', () => {
    expect(TRACE_COLORS.gyro).toBe('#ffffff');
    expect(Object.keys(TRACE_COLORS).length).toBeGreaterThan(5);
  });

  it('returns light plot layout colors', () => {
    const layout = getPlotLayoutBase('light');
    expect(layout.paper_bgcolor).toBe('#f5f5f5');
    expect(layout.font.color).toBe('#1a1a1a');
  });

  it('adapts low-contrast line colors for light theme', () => {
    expect(adaptPlotLineColor('#ffffff', 'light')).toBe('#1a1a1a');
    expect(adaptPlotLineColor('#ffffff', 'dark')).toBe('#ffffff');
  });

  it('maps trace panel titles by axis', () => {
    expect(tracePanelTitle('gyro', 'roll')).toBe('Roll rate');
    expect(tracePanelTitle('attitude', 'pitch')).toBe('Pitch');
    expect(tracePanelTitle('accel', 'yaw')).toBe('AccZ');
    expect(tracePanelTitle('velocity_sp', 'roll')).toBe('Vx_SP');
    expect(tracePanelTitle('setpoint', 'pitch')).toBe('Pitch rate_SP');
  });
});

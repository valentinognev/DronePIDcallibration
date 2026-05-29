import { describe, expect, it } from 'vitest';
import { buildMotorPanelCaption, buildPanelCaption, computeTraceYRange } from './utils';

describe('buildPanelCaption', () => {
  it('uses axis-specific rate and angle names', () => {
    const { title, yLabel } = buildPanelCaption('roll', [
      { key: 'gyro' },
      { key: 'attitude' },
    ]);
    expect(title).toBe('Roll rate, Roll');
    expect(yLabel).toBe('deg/s, deg');
  });

  it('names accel and velocity per axis', () => {
    const { title } = buildPanelCaption('pitch', [
      { key: 'accel' },
      { key: 'velocity_sp' },
    ]);
    expect(title).toBe('AccY, Vy_SP');
  });

  it('appends _SP to rate setpoint', () => {
    const { title } = buildPanelCaption('yaw', [{ key: 'setpoint' }]);
    expect(title).toBe('Yaw rate_SP');
  });
});

describe('buildMotorPanelCaption', () => {
  it('combines throttle and motor units', () => {
    const { title, yLabel } = buildMotorPanelCaption(
      [{ key: 'throttle' }, { key: 'motor_0' }],
      'rpm',
    );
    expect(title).toBe('Throttle, Motor 1');
    expect(yLabel).toBe('% | RPM');
  });
});

describe('computeTraceYRange', () => {
  it('returns undefined for no traces', () => {
    expect(computeTraceYRange([])).toBeUndefined();
  });

  it('pads min/max across all traces', () => {
    const range = computeTraceYRange([
      { y: [0, 100] },
      { y: [-50, 50] },
    ]);
    expect(range).toEqual([-57.5, 107.5]);
  });

  it('expands flat traces', () => {
    const range = computeTraceYRange([{ y: [10, 10, 10] }]);
    expect(range![0]).toBeLessThan(10);
    expect(range![1]).toBeGreaterThan(10);
  });
});

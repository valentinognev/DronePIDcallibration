import { describe, expect, it } from 'vitest';
import { TRACE_COLORS } from '../lib/constants';

describe('constants', () => {
  it('has trace colors defined', () => {
    expect(TRACE_COLORS.gyro).toBe('#ffffff');
    expect(Object.keys(TRACE_COLORS).length).toBeGreaterThan(5);
  });
});

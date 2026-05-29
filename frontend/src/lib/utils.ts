import {
  type AxisKey,
  TRACE_LABELS,
  TRACE_Y_UNITS,
  tracePanelTitle,
} from './constants';

/** Plot title and Y-axis label from visible traces on an R/P/Y panel. */
export function buildPanelCaption(
  axis: AxisKey,
  traces: { key: string }[],
): { title: string; yLabel: string } {
  if (traces.length === 0) {
    const fallback = axis.charAt(0).toUpperCase() + axis.slice(1);
    return { title: fallback, yLabel: fallback };
  }

  const keys = traces.map((t) => t.key);
  const names = keys.map((k) => tracePanelTitle(k, axis));
  const units = [
    ...new Set(
      keys.map((k) => TRACE_Y_UNITS[k]).filter((u): u is string => Boolean(u)),
    ),
  ];

  const title = names.join(', ');
  const yLabel =
    units.length === 0
      ? 'Value'
      : units.length === 1
        ? units[0]
        : units.join(', ');

  return { title, yLabel };
}

/** Title and Y-axis label for throttle / motor panel(s). */
export function buildMotorPanelCaption(
  traces: { key: string }[],
  motorsUnit: 'rpm' | 'percent',
): { title: string; yLabel: string } {
  if (traces.length === 0) {
    return { title: 'Motors', yLabel: 'Value' };
  }

  const names = traces.map((t) => TRACE_LABELS[t.key] ?? t.key);
  const units = [
    ...new Set(
      traces.map((t) => {
        if (t.key === 'throttle') return '%';
        if (t.key.startsWith('motor_in_')) return '%';
        if (t.key.startsWith('motor_')) return motorsUnit === 'rpm' ? 'RPM' : '%';
        return TRACE_Y_UNITS[t.key] ?? '';
      }).filter(Boolean),
    ),
  ];

  const title = names.join(', ');
  const yLabel = units.length <= 1 ? (units[0] ?? 'Value') : units.join(' | ');

  return { title, yLabel };
}

/** Y-axis range from visible trace samples, with padding (for Log Viewer autoscale). */
export function computeTraceYRange(
  traces: { y: number[] }[],
  paddingRatio = 0.05,
): [number, number] | undefined {
  if (traces.length === 0) return undefined;

  let min = Infinity;
  let max = -Infinity;
  for (const trace of traces) {
    for (const v of trace.y) {
      if (Number.isFinite(v)) {
        min = Math.min(min, v);
        max = Math.max(max, v);
      }
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return undefined;

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1);
    return [min - pad, max + pad];
  }

  const span = max - min;
  const pad = span * paddingRatio;
  return [min - pad, max + pad];
}

/** Save Plotly figure as PNG using browser download */
export async function savePlotlyFigure(plotElement: HTMLElement, filename: string) {
  const Plotly = await import('plotly.js');
  await Plotly.downloadImage(plotElement, {
    format: 'png',
    width: 1920,
    height: 1080,
    filename: filename.replace(/\.[^.]+$/, ''),
  });
}

/** Keyboard shortcut handler */
export function useKeyboardShortcuts(handlers: Record<string, () => void>) {
  if (typeof window === 'undefined') return;

  const onKey = (e: KeyboardEvent) => {
    const key = `${e.ctrlKey || e.metaKey ? 'ctrl+' : ''}${e.key.toLowerCase()}`;
    if (handlers[key]) {
      e.preventDefault();
      handlers[key]();
    }
  };

  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}

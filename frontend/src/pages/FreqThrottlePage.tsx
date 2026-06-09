import { useEffect, useRef, useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { ColormapPicker } from '../components/ColormapPicker';
import { api } from '../lib/api';
import { AXIS_LABELS, INTERACTIVE_PLOT_CONFIG, type AxisKey, tracePanelTitle } from '../lib/constants';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const GRID_TRACES = ['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint'] as const;
const AXIS_KEYS: AxisKey[] = ['roll', 'pitch', 'yaw'];
const MIN_PLOT_HEIGHT = 400;
const DEFAULT_PLOT_HEIGHT = 580;
const X_AXIS_LABEL = '% Throttle';

interface ThrottleResult {
  trace: string;
  freq: number[];
  amp: number[][];
  throttle: number[];
}

export function FreqThrottlePage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, selectedFileIdx } = useSessionStore();
  const [results, setResults] = useState<ThrottleResult[]>([]);
  const [resultsAxis, setResultsAxis] = useState<number | null>(null);
  const [axis, setAxis] = useState(0);
  const [colormap, setColormap] = useState('Hot');
  const [loading, setLoading] = useState(false);
  const [enabledTraces, setEnabledTraces] = useState<string[]>([...GRID_TRACES]);
  const plotAreaRef = useRef<HTMLDivElement>(null);
  const plotCellRef = useRef<HTMLDivElement>(null);
  const [plotHeight, setPlotHeight] = useState(DEFAULT_PLOT_HEIGHT);
  const [plotWidth, setPlotWidth] = useState<number | null>(null);

  useEffect(() => {
    setPlotWidth(null);
  }, [results.length]);

  useEffect(() => {
    const area = plotAreaRef.current;
    const cell = plotCellRef.current;
    if (!area || !cell || results.length === 0) return;

    const measure = () => {
      const areaRect = area.getBoundingClientRect();
      const h = Math.floor(areaRect.height);
      if (h >= MIN_PLOT_HEIGHT) setPlotHeight(h);

      const w = Math.floor(cell.getBoundingClientRect().width);
      if (w > 0) setPlotWidth(w);
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(area);
    ro.observe(cell);
    return () => ro.disconnect();
  }, [results.length]);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const next: ThrottleResult[] = [];
      for (const trace of enabledTraces) {
        const result = await api.runThrottleSpectrum({
          session_id: sessionId,
          file_idx: selectedFileIdx,
          axis,
          trace,
          psd: true,
        });
        next.push({
          trace,
          freq: (result.freq_hz as number[]) || [],
          amp: (result.amp_matrix as number[][]) || [],
          throttle: (result.throttle_bins as number[]) || [],
        });
      }
      setResults(next);
      setResultsAxis(axis);
    } finally {
      setLoading(false);
    }
  };

  const axisStale = results.length > 0 && resultsAxis !== null && axis !== resultsAxis;
  const titleAxis = resultsAxis ?? axis;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 flex flex-col gap-2 min-h-0 min-w-0 w-full">
        {axisStale && (
          <p className="text-sm text-amber-400 shrink-0">
            Axis changed to {AXIS_LABELS[axis]} — press <strong>Run</strong> to recalculate
            heatmaps and update titles.
          </p>
        )}
        {results.length === 0 ? (
          <div className="panel flex items-center justify-center text-sm text-[var(--text-secondary)] h-[600px]">
            Run analysis to display heatmaps
          </div>
        ) : (
          <div className="flex flex-col flex-1 min-h-0 min-w-0 w-full gap-1">
            <div
              className="grid w-full gap-x-1 shrink-0"
              style={{
                gridTemplateColumns: `1.25rem repeat(${results.length}, minmax(0, 1fr))`,
              }}
            >
              <div aria-hidden />
              {results.map(({ trace }) => (
                <h3
                  key={`${trace}-title`}
                  className="text-sm font-semibold text-center text-[var(--text-primary)] min-w-0"
                >
                  {tracePanelTitle(trace, AXIS_KEYS[titleAxis])}
                </h3>
              ))}
            </div>
            <div
              ref={plotAreaRef}
              className="grid flex-1 min-h-0 min-w-0 w-full gap-x-1"
              style={{
                gridTemplateColumns: `1.25rem repeat(${results.length}, minmax(0, 1fr))`,
              }}
            >
              <div
                className="flex items-center justify-center self-stretch h-full text-xs text-[var(--text-secondary)]"
                aria-hidden
              >
                <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap">
                  Frequency (Hz)
                </span>
              </div>
              {results.map(({ trace, freq, amp, throttle }, idx) => (
                <div
                  key={trace}
                  ref={idx === 0 ? plotCellRef : undefined}
                  data-plot-cell
                  className="min-w-0 w-full h-full overflow-hidden"
                >
                  {plotWidth !== null && (
                    <Plot
                      data={[
                        {
                          x: throttle,
                          y: freq.slice(0, amp[0]?.length || 0),
                          z: amp.map((row) => row.slice(0, freq.length)).slice(0, 100),
                          type: 'heatmap',
                          colorscale: colormap,
                        },
                      ]}
                      layout={{
                        ...plotLayoutBase,
                        width: plotWidth,
                        height: plotHeight,
                        margin: { ...plotLayoutBase.margin, t: 10, l: 42, r: 10, b: 36 },
                        xaxis: { ...plotLayoutBase.xaxis, title: '' },
                        yaxis: { ...plotLayoutBase.yaxis, title: '' },
                      }}
                      config={INTERACTIVE_PLOT_CONFIG}
                      style={{ width: plotWidth, height: plotHeight }}
                      useResizeHandler
                    />
                  )}
                </div>
              ))}
            </div>
            <div
              className="grid w-full shrink-0 gap-x-1"
              style={{
                gridTemplateColumns: `1.25rem repeat(${results.length}, minmax(0, 1fr))`,
              }}
            >
              <div aria-hidden />
              {results.map(({ trace }) => (
                <p
                  key={`${trace}-xlabel`}
                  className="text-xs text-center text-[var(--text-secondary)] min-w-0"
                >
                  {X_AXIS_LABEL}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Params</h3>
        <AxisSelector selected={axis} onChange={setAxis} />
        {axisStale && (
          <p className="text-xs text-amber-400">
            Showing {AXIS_LABELS[resultsAxis!]} data. Press <strong>Run</strong> after changing
            R / P / Y.
          </p>
        )}
        <div className="text-xs font-medium">Traces (columns)</div>
        {GRID_TRACES.map((t) => (
          <label key={t} className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabledTraces.includes(t)}
              onChange={() =>
                setEnabledTraces((s) =>
                  s.includes(t) ? s.filter((x) => x !== t) : [...s, t],
                )
              }
            />
            {t}
          </label>
        ))}
        <ColormapPicker value={colormap} onChange={setColormap} />
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId || enabledTraces.length === 0}>
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  );
}

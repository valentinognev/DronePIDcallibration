import { useEffect, useRef, useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { ColormapPicker } from '../components/ColormapPicker';
import { api } from '../lib/api';
import { AXIS_LABELS, INTERACTIVE_PLOT_CONFIG, type AxisKey, tracePanelTitle } from '../lib/constants';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const AXIS_KEYS: AxisKey[] = ['roll', 'pitch', 'yaw'];
const X_AXIS_LABEL = 'Time (s)';
const Y_AXIS_LABEL = 'Frequency (Hz)';
const MIN_PLOT_HEIGHT = 400;
const DEFAULT_PLOT_HEIGHT = 600;

export function FreqTimePage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, selectedFileIdx } = useSessionStore();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [resultsAxis, setResultsAxis] = useState<number | null>(null);
  const [axis, setAxis] = useState(0);
  const [trace, setTrace] = useState('gyro');
  const [colormap, setColormap] = useState('Hot');
  const [loading, setLoading] = useState(false);
  const plotAreaRef = useRef<HTMLDivElement>(null);
  const [plotHeight, setPlotHeight] = useState(DEFAULT_PLOT_HEIGHT);

  useEffect(() => {
    const area = plotAreaRef.current;
    if (!area || !data) return;

    const measure = () => {
      const h = Math.floor(area.getBoundingClientRect().height);
      if (h >= MIN_PLOT_HEIGHT) setPlotHeight(h);
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(area);
    return () => ro.disconnect();
  }, [data]);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.runTimeFreq({
        session_id: sessionId,
        file_idx: selectedFileIdx,
        axis,
        trace,
        smooth_factor: 1,
        subsample_factor: 1,
      });
      setData(result);
      setResultsAxis(axis);
    } finally {
      setLoading(false);
    }
  };

  const timeSec = (data?.time_sec as number[]) || [];
  const freq = (data?.freq_hz as number[]) || [];
  const spec = (data?.spec_matrix as number[][]) || [];
  const axisStale = data !== null && resultsAxis !== null && axis !== resultsAxis;
  const titleAxis = resultsAxis ?? axis;
  const panelTitle = tracePanelTitle(trace, AXIS_KEYS[titleAxis]);

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 flex flex-col gap-2 min-h-0 min-w-0 w-full">
        {axisStale && (
          <p className="text-sm text-amber-400 shrink-0">
            Axis changed to {AXIS_LABELS[axis]} — press <strong>Run</strong> to recalculate the
            heatmap and update the title.
          </p>
        )}
        {data === null ? (
          <div className="panel flex items-center justify-center text-sm text-[var(--text-secondary)] h-[600px]">
            Run analysis to display heatmap
          </div>
        ) : (
          <div className="flex flex-col flex-1 min-h-0 min-w-0 w-full gap-1">
            <h3 className="text-sm font-semibold text-center text-[var(--text-primary)] shrink-0">
              {panelTitle}
            </h3>
            <div
              ref={plotAreaRef}
              className="grid flex-1 min-h-0 min-w-0 w-full gap-x-1"
              style={{ gridTemplateColumns: '1.25rem 1fr' }}
            >
              <div
                className="flex items-center justify-center self-stretch h-full text-xs text-[var(--text-secondary)]"
                aria-hidden
              >
                <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap">
                  {Y_AXIS_LABEL}
                </span>
              </div>
              <div className="min-w-0 w-full h-full overflow-hidden">
                <Plot
                  data={[
                    {
                      x: timeSec,
                      y: freq,
                      z: spec,
                      type: 'heatmap',
                      colorscale: colormap,
                    },
                  ]}
                  layout={{
                    ...plotLayoutBase,
                    height: plotHeight,
                    margin: { ...plotLayoutBase.margin, t: 10, l: 42, r: 10, b: 36 },
                    xaxis: { ...plotLayoutBase.xaxis, title: '' },
                    yaxis: { ...plotLayoutBase.yaxis, title: '' },
                  }}
                  config={INTERACTIVE_PLOT_CONFIG}
                  style={{ width: '100%', height: plotHeight }}
                  useResizeHandler
                />
              </div>
            </div>
            <p className="text-xs text-center text-[var(--text-secondary)] shrink-0">
              {X_AXIS_LABEL}
            </p>
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
        <select className="select-input" value={trace} onChange={(e) => setTrace(e.target.value)}>
          {['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr'].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <ColormapPicker value={colormap} onChange={setColormap} />
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  );
}

import { useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { ColormapPicker } from '../components/ColormapPicker';
import { api } from '../lib/api';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const GRID_TRACES = ['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint'] as const;

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
  const [axis, setAxis] = useState(0);
  const [colormap, setColormap] = useState('Hot');
  const [loading, setLoading] = useState(false);
  const [enabledTraces, setEnabledTraces] = useState<string[]>([...GRID_TRACES]);

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
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 overflow-x-auto">
        <div
          className="grid gap-2 min-w-full"
          style={{ gridTemplateColumns: `repeat(${Math.max(results.length, 1)}, minmax(280px, 1fr))` }}
        >
          {results.length === 0 ? (
            <div className="panel flex items-center justify-center text-sm text-[var(--text-secondary)] h-[600px]">
              Run analysis to display heatmaps
            </div>
          ) : (
            results.map(({ trace, freq, amp, throttle }) => (
              <Plot
                key={trace}
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
                  title: trace,
                  height: 600,
                  xaxis: { title: '% Throttle' },
                  yaxis: { title: 'Frequency (Hz)' },
                }}
                config={{ responsive: true }}
                style={{ width: '100%' }}
                useResizeHandler
              />
            ))
          )}
        </div>
      </div>
      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Params</h3>
        <AxisSelector selected={axis} onChange={setAxis} />
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

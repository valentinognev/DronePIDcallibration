import { useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { ColormapPicker } from '../components/ColormapPicker';
import { api } from '../lib/api';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

export function FreqThrottlePage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, selectedFileIdx } = useSessionStore();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [axis, setAxis] = useState(0);
  const [trace, setTrace] = useState('gyro');
  const [colormap, setColormap] = useState('Hot');
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.runThrottleSpectrum({
        session_id: sessionId,
        file_idx: selectedFileIdx,
        axis,
        trace,
        psd: true,
      });
      setData(result);
    } finally {
      setLoading(false);
    }
  };

  const freq = (data?.freq_hz as number[]) || [];
  const amp = (data?.amp_matrix as number[][]) || [];
  const throttle = (data?.throttle_bins as number[]) || [];

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1">
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
            title: `Frequency × Throttle — ${trace}`,
            height: 600,
            xaxis: { title: '% Throttle' },
            yaxis: { title: 'Frequency (Hz)' },
          }}
          config={{ responsive: true }}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </div>
      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Params</h3>
        <AxisSelector selected={axis} onChange={setAxis} />
        <select className="select-input" value={trace} onChange={(e) => setTrace(e.target.value)}>
          {['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint'].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <ColormapPicker value={colormap} onChange={setColormap} />
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
          Run
        </button>
      </div>
    </div>
  );
}

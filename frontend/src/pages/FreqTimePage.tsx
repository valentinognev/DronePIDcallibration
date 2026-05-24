import { useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { ColormapPicker } from '../components/ColormapPicker';
import { PLOT_LAYOUT_BASE } from '../lib/constants';
import { api } from '../lib/api';
import { useSessionStore } from '../store/sessionStore';

export function FreqTimePage() {
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
      const result = await api.runTimeFreq({
        session_id: sessionId,
        file_idx: selectedFileIdx,
        axis,
        trace,
        smooth_factor: 1,
        subsample_factor: 1,
      });
      setData(result);
    } finally {
      setLoading(false);
    }
  };

  const timeSec = (data?.time_sec as number[]) || [];
  const freq = (data?.freq_hz as number[]) || [];
  const spec = (data?.spec_matrix as number[][]) || [];

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1">
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
            ...PLOT_LAYOUT_BASE,
            title: `Frequency × Time — ${trace}`,
            height: 600,
            xaxis: { title: 'Time (s)' },
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
          {['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr'].map((t) => (
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

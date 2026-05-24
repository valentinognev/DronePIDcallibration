import { useState } from 'react';
import Plot from '../components/Plot';
import { adaptPlotLineColor } from '../lib/constants';
import { api } from '../lib/api';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';

export function FilterSimPage() {
  const theme = useAppTheme();
  const plotLayoutBase = usePlotLayoutBase();
  const [looprate, setLooprate] = useState(8000);
  const [lpf1, setLpf1] = useState(250);
  const [lpf2, setLpf2] = useState(500);
  const [notchFreq, setNotchFreq] = useState(100);
  const [notchQ, setNotchQ] = useState(500);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const result = await api.runFilterSim({
        looprate_hz: looprate,
        lpf_cutoffs: [lpf1, lpf2].filter((x) => x > 0),
        notch_configs: [
          [notchFreq, notchQ],
          [notchFreq * 2, notchQ],
          [notchFreq * 3, notchQ],
        ],
      });
      setData(result);
    } finally {
      setLoading(false);
    }
  };

  const lpf = (data?.lpf as Array<Record<string, number[]>>) || [];
  const notch = (data?.notch as Array<Record<string, number[]>>) || [];
  const combined = data?.combined as Record<string, number[]> | undefined;

  const plotPanel = (responses: Array<Record<string, number[]>>, title: string, colors: string[]) => (
    <div className="grid grid-rows-4 gap-1">
      {['magnitude_db', 'group_delay_ms', 'phase_deg', 'step_response'].map((key, ki) => (
        <Plot
          key={key}
          data={responses.map((r, i) => ({
            x: key === 'step_response' ? r.step_time_ms : r.freq_hz,
            y: r[key],
            type: 'scatter',
            mode: 'lines',
            name: `${title} ${i + 1}`,
            line: { color: colors[i % colors.length] },
            xaxis: key === 'step_response' ? undefined : 'x',
          }))}
          layout={{
            ...plotLayoutBase,
            title: `${title} — ${key.replace('_', ' ')}`,
            height: 180,
            showlegend: ki === 0,
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
          useResizeHandler
        />
      ))}
    </div>
  );

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid grid-cols-2 gap-2 overflow-auto">
        {plotPanel(lpf, 'Lowpass', ['#00cccc', '#00ff00'])}
        {plotPanel(notch, 'Notch', ['#ff0000', '#ff9900', '#ffff00'])}
        {combined && (
          <div className="col-span-2">
            <Plot
              data={[
                {
                  x: combined.freq_hz,
                  y: combined.magnitude_db,
                  type: 'scatter',
                  mode: 'lines',
                  name: 'Combined',
                  line: { color: adaptPlotLineColor('#ffffff', theme) },
                },
              ]}
              layout={{
                ...plotLayoutBase,
                title: `Combined | Total Delay: ${Number(data?.total_delay_ms).toFixed(3)} ms`,
                height: 200,
                xaxis: { title: 'Frequency (Hz)' },
                yaxis: { title: 'Magnitude (dB)' },
              }}
              config={{ responsive: true }}
              style={{ width: '100%' }}
            />
          </div>
        )}
      </div>

      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Filter Controls</h3>
        <label className="text-xs">Looprate (Hz)</label>
        <input className="select-input" type="number" value={looprate} onChange={(e) => setLooprate(Number(e.target.value))} />
        <label className="text-xs">LPF pt1 #1 (Hz)</label>
        <input className="select-input" type="number" value={lpf1} onChange={(e) => setLpf1(Number(e.target.value))} />
        <label className="text-xs">LPF pt1 #2 (Hz)</label>
        <input className="select-input" type="number" value={lpf2} onChange={(e) => setLpf2(Number(e.target.value))} />
        <label className="text-xs">Notch freq (Hz)</label>
        <input className="select-input" type="number" value={notchFreq} onChange={(e) => setNotchFreq(Number(e.target.value))} />
        <label className="text-xs">Notch Q</label>
        <input className="select-input" type="number" value={notchQ} onChange={(e) => setNotchQ(Number(e.target.value))} />
        <button className="btn-run w-full" onClick={run} disabled={loading}>
          Run
        </button>
        {data && (
          <p className="text-red-400 text-sm font-semibold">
            Filter Delay Total: {Number(data.total_delay_ms).toFixed(4)} ms
          </p>
        )}
      </div>
    </div>
  );
}

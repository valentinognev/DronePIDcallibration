import { useState } from 'react';
import Plot from '../components/Plot';
import { PLOT_LAYOUT_BASE } from '../lib/constants';
import { api } from '../lib/api';
import { useSessionStore } from '../store/sessionStore';

export function SpectralAnalyzerPage() {
  const { sessionId, files } = useSessionStore();
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [traces, setTraces] = useState(['gyro', 'gyro_pf']);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([0]);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const data = await api.runSpectrum({
        session_id: sessionId,
        file_indices: selectedFiles,
        axes: [0, 1, 2],
        traces,
        psd: true,
        sub100hz: true,
      });
      setResults(data.results);
    } finally {
      setLoading(false);
    }
  };

  const resultList = results;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid grid-cols-2 grid-rows-3 gap-2">
        {['roll', 'pitch', 'yaw'].flatMap((axis) => [
          <SpectrumPanel key={`${axis}-full`} resultList={resultList} axis={axis} sub={false} />,
          <SpectrumPanel key={`${axis}-sub`} resultList={resultList} axis={axis} sub={true} />,
        ])}
      </div>

      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Params</h3>
        <div className="text-xs">Files ({files.length})</div>
        {files.map((f, i) => (
          <label key={f.file_id} className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={selectedFiles.includes(i)}
              onChange={() =>
                setSelectedFiles((s) =>
                  s.includes(i) ? s.filter((x) => x !== i) : [...s, i].slice(0, 10),
                )
              }
            />
            {f.original_name.slice(0, 20)}
          </label>
        ))}
        {['gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint'].map((t) => (
          <label key={t} className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={traces.includes(t)}
              onChange={() =>
                setTraces((tr) => (tr.includes(t) ? tr.filter((x) => x !== t) : [...tr, t]))
              }
            />
            {t}
          </label>
        ))}
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  );
}

function SpectrumPanel({
  resultList,
  axis,
  sub,
}: {
  resultList: Array<Record<string, unknown>>;
  axis: string;
  sub: boolean;
}) {
  const traces: Plotly.Data[] = [];
  const colors = ['#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff'];

  resultList.forEach((file, fi) => {
    const axes = file.axes as Record<string, Record<string, { freq: number[]; spec: number[]; freq_sub?: number[]; spec_sub?: number[] }>>;
    const data = axes?.[axis];
    if (!data) return;
    Object.entries(data).forEach(([trace, spec], ti) => {
      const freq = sub ? spec.freq_sub || spec.freq : spec.freq;
      const specData = sub ? spec.spec_sub || spec.spec : spec.spec;
      if (!freq?.length) return;
      const mask = sub ? freq.map((f) => f <= 100) : freq.map(() => true);
      traces.push({
        x: freq.filter((_, i) => mask[i]),
        y: specData.filter((_, i) => mask[i]),
        type: 'scatter',
        mode: 'lines',
        name: `${trace} (${fi + 1})`,
        line: { color: colors[(fi + ti) % colors.length] },
      });
    });
  });

  return (
    <Plot
      data={traces}
      layout={{
        ...PLOT_LAYOUT_BASE,
        title: `${axis.charAt(0).toUpperCase() + axis.slice(1)} | ${sub ? 'Sub 100Hz' : 'Full Spectrum'}`,
        height: 220,
        xaxis: { ...PLOT_LAYOUT_BASE.xaxis, title: 'Frequency (Hz)' },
        yaxis: { ...PLOT_LAYOUT_BASE.yaxis, title: 'PSD (dB)' },
      }}
      config={{ responsive: true, displayModeBar: false }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  );
}

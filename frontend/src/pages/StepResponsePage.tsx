import { useState } from 'react';
import Plot from '../components/Plot';
import { api } from '../lib/api';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

export function StepResponsePage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, files } = useSessionStore();
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([0]);
  const [smoothFactor, setSmoothFactor] = useState(1);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const data = await api.runStepResponse({
        session_id: sessionId,
        file_indices: selectedFiles.slice(0, 10),
        smooth_factor: smoothFactor,
        y_correction: true,
      });
      setResults(data.results);
    } finally {
      setLoading(false);
    }
  };

  const colors = ['#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff'];

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid grid-rows-3 gap-2">
        {['roll', 'pitch', 'yaw'].map((axis) => {
          const traces: Plotly.Data[] = [];
          results.forEach((file, fi) => {
            const axes = file.axes as Record<string, { time_ms: number[]; curves: number[][]; mean_curve: number[]; stats: Record<string, number>; pidf: string }>;
            const ax = axes?.[axis];
            if (!ax?.time_ms) return;
            if (ax.mean_curve?.length) {
              traces.push({
                x: ax.time_ms,
                y: ax.mean_curve,
                type: 'scatter',
                mode: 'lines',
                name: `${file.name} (${ax.stats?.n || 0})`,
                line: { color: colors[fi % colors.length] },
              });
            }
          });

          return (
            <div key={axis} className="flex gap-2">
              <Plot
                data={traces}
                layout={{
                  ...plotLayoutBase,
                  title: `${axis.charAt(0).toUpperCase() + axis.slice(1)} Step Response`,
                  height: 250,
                  xaxis: { ...plotLayoutBase.xaxis, title: 'Time (ms)' },
                  yaxis: { ...plotLayoutBase.yaxis, title: 'Response', range: [0, 1.5] },
                }}
                config={{ responsive: true }}
                style={{ width: '70%' }}
                useResizeHandler
              />
              <div className="panel w-48 text-xs overflow-auto">
                <h4 className="font-semibold mb-2">{axis} stats</h4>
                {results.map((file, fi) => {
                  const ax = (file.axes as Record<string, { stats: Record<string, number>; pidf: string }>)?.[axis];
                  if (!ax) return null;
                  return (
                    <div key={fi} className="mb-2" style={{ color: colors[fi % colors.length] }}>
                      <p>{String(file.name)}</p>
                      <p>{ax.pidf}</p>
                      <p>Peak: {ax.stats.peak_mean?.toFixed(3)} ± {ax.stats.peak_std?.toFixed(3)}</p>
                      <p>Latency: {ax.stats.latency_mean_ms?.toFixed(1)} ms</p>
                      <p>n={ax.stats.n}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Step Resp Tool</h3>
        {files.map((f, i) => (
          <label key={f.file_id} className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={selectedFiles.includes(i)}
              onChange={() =>
                setSelectedFiles((s) =>
                  s.includes(i) ? s.filter((x) => x !== i) : [...s, i],
                )
              }
            />
            {f.original_name.slice(0, 18)}
          </label>
        ))}
        <select className="select-input" value={smoothFactor} onChange={(e) => setSmoothFactor(Number(e.target.value))}>
          <option value={1}>smooth off</option>
          <option value={2}>smooth low</option>
          <option value={3}>smooth med</option>
          <option value={4}>smooth high</option>
        </select>
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
          Run
        </button>
      </div>
    </div>
  );
}

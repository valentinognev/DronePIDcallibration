import { useState } from 'react';
import Plot from '../components/Plot';
import { api } from '../lib/api';
import { FILE_OVERLAY_COLORS } from '../lib/constants';
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
                line: { color: FILE_OVERLAY_COLORS[fi % FILE_OVERLAY_COLORS.length] },
              });
            }
          });

          const fileStats = results
            .map((file, fi) => {
              const ax = (file.axes as Record<string, { stats: Record<string, number>; pidf: string }>)?.[axis];
              if (!ax?.stats) return null;
              return { name: String(file.name), fi, stats: ax.stats, pidf: ax.pidf };
            })
            .filter(Boolean) as Array<{ name: string; fi: number; stats: Record<string, number>; pidf: string }>;

          const barNames = fileStats.map((f) => f.name.slice(0, 12));
          const peakBars: Plotly.Data = {
            type: 'bar',
            x: barNames,
            y: fileStats.map((f) => f.stats.peak_mean ?? 0),
            marker: { color: fileStats.map((f) => FILE_OVERLAY_COLORS[f.fi % FILE_OVERLAY_COLORS.length]) },
            name: 'Peak',
          };
          const latencyBars: Plotly.Data = {
            type: 'bar',
            x: barNames,
            y: fileStats.map((f) => f.stats.latency_mean_ms ?? 0),
            marker: { color: fileStats.map((f) => FILE_OVERLAY_COLORS[f.fi % FILE_OVERLAY_COLORS.length]) },
            name: 'Latency (ms)',
          };

          return (
            <div key={axis} className="flex gap-2 min-h-0">
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
                style={{ width: '45%' }}
                useResizeHandler
              />
              <div className="flex flex-col gap-1 w-[55%] min-h-0">
                <Plot
                  data={[peakBars]}
                  layout={{
                    ...plotLayoutBase,
                    title: `${axis} — Peak`,
                    height: 120,
                    margin: { l: 40, r: 10, t: 30, b: 30 },
                    yaxis: { ...plotLayoutBase.yaxis, title: 'Peak', range: [0, 1.5] },
                    showlegend: false,
                  }}
                  config={{ responsive: true, displayModeBar: false }}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
                <Plot
                  data={[latencyBars]}
                  layout={{
                    ...plotLayoutBase,
                    title: `${axis} — Latency`,
                    height: 120,
                    margin: { l: 40, r: 10, t: 30, b: 30 },
                    yaxis: { ...plotLayoutBase.yaxis, title: 'ms' },
                    showlegend: false,
                  }}
                  config={{ responsive: true, displayModeBar: false }}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
                <div className="panel text-xs overflow-auto flex-1 min-h-0">
                  <h4 className="font-semibold mb-1">{axis} stats</h4>
                  {fileStats.map(({ name, fi, stats, pidf }) => (
                    <div key={fi} className="mb-1" style={{ color: FILE_OVERLAY_COLORS[fi % FILE_OVERLAY_COLORS.length] }}>
                      <p>{name}</p>
                      <p>{pidf}</p>
                      <p>Peak: {stats.peak_mean?.toFixed(3)} ± {stats.peak_std?.toFixed(3)}</p>
                      <p>Latency: {stats.latency_mean_ms?.toFixed(1)} ms · n={stats.n}</p>
                    </div>
                  ))}
                </div>
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

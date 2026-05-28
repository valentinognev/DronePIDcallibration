import { useState } from 'react';
import Plot from '../components/Plot';
import { api, type StepAxisResult, type StepAxisStats, type StepResponseResult } from '../lib/api';
import { AXIS_LABELS, FILE_OVERLAY_COLORS, STEP_SIGNAL_MODES, type StepSignalMode } from '../lib/constants';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const AXES = ['roll', 'pitch', 'yaw'] as const;

function getAxisResult(
  file: StepResponseResult,
  signal: StepSignalMode,
  axis: (typeof AXES)[number],
): StepAxisResult | undefined {
  if (signal === 'rate' && file.axes) {
    return file.axes[axis];
  }
  return file.signals?.[signal]?.[axis];
}

function signalLabel(signal: StepSignalMode): string {
  return STEP_SIGNAL_MODES.find((m) => m.key === signal)?.label ?? signal;
}

export function StepResponsePage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, files } = useSessionStore();
  const [results, setResults] = useState<StepResponseResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([0]);
  const [smoothFactor, setSmoothFactor] = useState(1);
  const [selectedSignals, setSelectedSignals] = useState<StepSignalMode[]>(['rate']);

  const toggleSignal = (signal: StepSignalMode) => {
    setSelectedSignals((prev) => {
      if (prev.includes(signal)) {
        const next = prev.filter((s) => s !== signal);
        return next.length > 0 ? next : prev;
      }
      return [...prev, signal];
    });
  };

  const run = async () => {
    if (!sessionId || selectedSignals.length === 0) return;
    setLoading(true);
    try {
      const data = await api.runStepResponse({
        session_id: sessionId,
        file_indices: selectedFiles.slice(0, 10),
        smooth_factor: smoothFactor,
        y_correction: true,
        signals: selectedSignals,
      });
      setResults(data.results);
    } finally {
      setLoading(false);
    }
  };

  const panels = selectedSignals.flatMap((signal) =>
    AXES.map((axis) => ({ signal, axis })),
  );

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid gap-2 overflow-y-auto" style={{ gridTemplateRows: `repeat(${panels.length}, minmax(250px, auto))` }}>
        {panels.map(({ signal, axis }) => {
          const axisIdx = AXES.indexOf(axis);
          const axisName = AXIS_LABELS[axisIdx];
          const traces: Plotly.Data[] = [];
          results.forEach((file, fi) => {
            const ax = getAxisResult(file, signal, axis);
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
              const ax = getAxisResult(file, signal, axis);
              if (!ax?.stats) return null;
              return { name: String(file.name), fi, stats: ax.stats, pidf: ax.pidf };
            })
            .filter(Boolean) as Array<{ name: string; fi: number; stats: StepAxisStats; pidf?: string }>;

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
            <div key={`${signal}-${axis}`} className="flex gap-2 min-h-0">
              <Plot
                data={traces}
                layout={{
                  ...plotLayoutBase,
                  title: `${axisName} — ${signalLabel(signal)} Step Response`,
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
                    title: `${axisName} — Peak`,
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
                    title: `${axisName} — Latency`,
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
                  <h4 className="font-semibold mb-1">{axisName} stats</h4>
                  {fileStats.map(({ name, fi, stats, pidf }) => (
                    <div key={fi} className="mb-1" style={{ color: FILE_OVERLAY_COLORS[fi % FILE_OVERLAY_COLORS.length] }}>
                      <p>{name}</p>
                      {pidf && <p>{pidf}</p>}
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
        <div>
          <p className="text-xs text-[var(--text-secondary)] mb-1">Signal modes</p>
          {STEP_SIGNAL_MODES.map(({ key, label }) => (
            <label key={key} className="flex gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedSignals.includes(key)}
                onChange={() => toggleSignal(key)}
              />
              {label}
            </label>
          ))}
        </div>
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

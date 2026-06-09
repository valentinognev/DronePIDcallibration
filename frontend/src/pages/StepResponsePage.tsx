import { useState } from 'react';
import Plot from '../components/Plot';
import { api, type StepAxisResult, type StepAxisStats, type StepResponseResult } from '../lib/api';
import {
  AXIS_LABELS,
  FILE_OVERLAY_COLORS,
  STEP_SIGNAL_LINE_STYLES,
  INTERACTIVE_PLOT_CONFIG,
  STEP_SIGNAL_MARKER_SYMBOLS,
  STEP_SIGNAL_MODES,
  stepSignalPointMarker,
  type StepSignalMode,
} from '../lib/constants';
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

function traceName(
  file: StepResponseResult,
  signal: StepSignalMode,
  axis: (typeof AXES)[number],
  multiFile: boolean,
): string {
  const label = signalLabel(signal);
  if (!multiFile) return label;
  const n = getAxisResult(file, signal, axis)?.stats?.n;
  const count = n !== undefined ? ` (${n})` : '';
  return `${label} — ${file.name}${count}`;
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

  const activeResults = results.filter((file) => selectedFiles.includes(file.file_idx));
  const multiFile = activeResults.length > 1;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div
        className="flex-1 grid gap-2 overflow-y-auto"
        style={{ gridTemplateRows: `repeat(${AXES.length}, minmax(250px, auto))` }}
      >
        {AXES.map((axis) => {
          const axisIdx = AXES.indexOf(axis);
          const axisName = AXIS_LABELS[axisIdx];
          const traces: Plotly.Data[] = [];

          for (const signal of selectedSignals) {
            const lineStyle = STEP_SIGNAL_LINE_STYLES[signal];
            for (const file of activeResults) {
              const ax = getAxisResult(file, signal, axis);
              if (!ax?.time_ms || !ax.mean_curve?.length) continue;
              traces.push({
                x: ax.time_ms,
                y: ax.mean_curve,
                type: 'scatter',
                mode: 'lines',
                name: traceName(file, signal, axis, multiFile),
                line: {
                  color: FILE_OVERLAY_COLORS[file.file_idx % FILE_OVERLAY_COLORS.length],
                  dash: lineStyle.dash,
                  width: lineStyle.width,
                },
              });
            }
          }

          type StatRow = {
            signal: StepSignalMode;
            name: string;
            fi: number;
            stats: StepAxisStats;
            pidf?: string;
          };

          const fileStats: StatRow[] = [];
          for (const signal of selectedSignals) {
            for (const file of activeResults) {
              const ax = getAxisResult(file, signal, axis);
              if (!ax?.stats) continue;
              fileStats.push({
                signal,
                name: String(file.name),
                fi: file.file_idx,
                stats: ax.stats,
                pidf: ax.pidf,
              });
            }
          }

          const pointX = fileStats.map((_, i) => i + 1);
          const pointMarker = stepSignalPointMarker(fileStats);
          const pointXaxis = {
            ...plotLayoutBase.xaxis,
            showticklabels: false,
            showgrid: false,
          };
          const pointAxis = {
            xaxis: pointXaxis,
            yaxis: {
              ...plotLayoutBase.yaxis,
              showgrid: true,
            },
          };
          const peakPoints: Plotly.Data = {
            type: 'scatter',
            mode: 'markers',
            x: pointX,
            y: fileStats.map((f) => f.stats.peak_mean ?? 0),
            marker: pointMarker,
            hovertext: fileStats.map(
              (f) => `${signalLabel(f.signal)} — ${f.name}`,
            ),
            hoverinfo: 'y+text',
            name: 'Peak',
          };
          const latencyPoints: Plotly.Data = {
            type: 'scatter',
            mode: 'markers',
            x: pointX,
            y: fileStats.map((f) => f.stats.latency_mean_ms ?? 0),
            marker: pointMarker,
            hovertext: fileStats.map(
              (f) => `${signalLabel(f.signal)} — ${f.name}`,
            ),
            hoverinfo: 'y+text',
            name: 'Latency (ms)',
          };

          if (traces.length === 0 && fileStats.length === 0) {
            return null;
          }

          const signalSummary = selectedSignals.map((s) => signalLabel(s)).join(', ');

          return (
            <div key={axis} className="grid grid-cols-[3fr_1fr_1fr] gap-2 min-h-0 w-full">
              <div className="min-w-0">
                <Plot
                  key={`${axis}-${traces.map((t) => t.name).join('|')}`}
                  data={traces}
                  layout={{
                    ...plotLayoutBase,
                    title: `${axisName} — Step Response (${signalSummary})`,
                    height: 250,
                    showlegend: traces.length > 1,
                    legend: { orientation: 'h', y: 1.12, x: 0 },
                    xaxis: { ...plotLayoutBase.xaxis, title: 'Time (ms)' },
                    yaxis: { ...plotLayoutBase.yaxis, title: 'Response', range: [0, 1.5] },
                  }}
                  config={INTERACTIVE_PLOT_CONFIG}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
              </div>
              <div className="flex flex-col gap-1 min-w-0 min-h-0">
                <h4 className="font-semibold text-xs shrink-0">{axisName} — Peak</h4>
                <Plot
                  data={[peakPoints]}
                  layout={{
                    ...plotLayoutBase,
                    height: 120,
                    margin: { l: 40, r: 4, t: 10, b: 8 },
                    ...pointAxis,
                    yaxis: { ...pointAxis.yaxis, range: [0, 1.5] },
                    showlegend: false,
                  }}
                  config={INTERACTIVE_PLOT_CONFIG}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
                <h4 className="font-semibold text-xs shrink-0">{axisName} — Latency (ms)</h4>
                <Plot
                  data={[latencyPoints]}
                  layout={{
                    ...plotLayoutBase,
                    height: 120,
                    margin: { l: 40, r: 4, t: 10, b: 8 },
                    ...pointAxis,
                    showlegend: false,
                  }}
                  config={INTERACTIVE_PLOT_CONFIG}
                  style={{ width: '100%' }}
                  useResizeHandler
                />
              </div>
              <div className="panel text-xs overflow-auto min-w-0 min-h-0 self-stretch">
                <h4 className="font-semibold mb-1 shrink-0">{axisName} — Stats</h4>
                {fileStats.map(({ signal, name, fi, stats, pidf }) => (
                  <div
                    key={`${fi}-${signal}`}
                    className="mb-1"
                    style={{ color: FILE_OVERLAY_COLORS[fi % FILE_OVERLAY_COLORS.length] }}
                  >
                    <p>
                      {signalLabel(signal)}
                      {multiFile ? ` — ${name}` : ''}
                      <span className="text-[var(--text-secondary)]">
                        {' '}
                        ({STEP_SIGNAL_LINE_STYLES[signal].dash},{' '}
                        {STEP_SIGNAL_MARKER_SYMBOLS[signal]})
                      </span>
                    </p>
                    {pidf && <p>{pidf}</p>}
                    <p>Peak: {stats.peak_mean?.toFixed(3)} ± {stats.peak_std?.toFixed(3)}</p>
                    <p>Latency: {stats.latency_mean_ms?.toFixed(1)} ms · n={stats.n}</p>
                  </div>
                ))}
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
              <span className="text-[var(--text-secondary)] text-xs">
                ({STEP_SIGNAL_LINE_STYLES[key].dash},{' '}
                {STEP_SIGNAL_MARKER_SYMBOLS[key]})
              </span>
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

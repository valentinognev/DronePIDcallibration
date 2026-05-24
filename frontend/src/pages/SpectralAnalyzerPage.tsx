import { useCallback, useRef, useState } from 'react';
import Plot from '../components/Plot';
import { api } from '../lib/api';
import { FILE_OVERLAY_COLORS, getTraceColor } from '../lib/constants';
import { savePlotlyFigure } from '../lib/utils';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const TRACE_OPTIONS = [
  'gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint',
  'motor_0', 'motor_1', 'motor_2', 'motor_3',
];

const MOTOR_PAIRS: Array<{ label: string; traces: string[] }> = [
  { label: 'Motors 1–2', traces: ['motor_0', 'motor_1'] },
  { label: 'Motors 3–4', traces: ['motor_2', 'motor_3'] },
];

export function SpectralAnalyzerPage() {
  const { sessionId, files, selectedFileIdx } = useSessionStore();
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [rpmOverlay, setRpmOverlay] = useState<{ freq: number[]; fundamental: number[]; harmonics: number[][] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [traces, setTraces] = useState(['gyro', 'gyro_pf']);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([0]);
  const [showRpmOverlay, setShowRpmOverlay] = useState(false);

  const toggleMotorPair = (pairTraces: string[], enabled: boolean) => {
    setTraces((current) => {
      const without = current.filter((t) => !pairTraces.includes(t));
      if (!enabled) return without;
      return [...without, ...pairTraces.filter((t) => !without.includes(t))];
    });
  };

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

      if (showRpmOverlay) {
        const rpmData = await api.runThrottleSpectrum({
          session_id: sessionId,
          file_idx: selectedFileIdx,
          axis: 0,
          trace: 'gyro',
          psd: true,
        });
        setRpmOverlay({
          freq: (rpmData.freq_hz as number[]) || [],
          fundamental: (rpmData.rpm_fundamental as number[]) || [],
          harmonics: (rpmData.rpm_harmonics as number[][]) || [],
        });
      } else {
        setRpmOverlay(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const resultList = results;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid grid-cols-2 grid-rows-3 gap-2">
        {['roll', 'pitch', 'yaw'].flatMap((axis) => [
          <SpectrumPanel key={`${axis}-full`} resultList={resultList} axis={axis} sub={false} rpmOverlay={rpmOverlay} />,
          <SpectrumPanel key={`${axis}-sub`} resultList={resultList} axis={axis} sub={true} rpmOverlay={rpmOverlay} />,
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
            <span style={{ color: FILE_OVERLAY_COLORS[i % FILE_OVERLAY_COLORS.length] }}>
              {f.original_name.slice(0, 20)}
            </span>
          </label>
        ))}

        <div className="text-xs font-medium pt-1">Motor pairs</div>
        {MOTOR_PAIRS.map(({ label, traces: pairTraces }) => (
          <label key={label} className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={pairTraces.every((t) => traces.includes(t))}
              onChange={(e) => toggleMotorPair(pairTraces, e.target.checked)}
            />
            {label}
          </label>
        ))}

        {TRACE_OPTIONS.map((t) => (
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

        <label className="flex gap-2 text-sm">
          <input
            type="checkbox"
            checked={showRpmOverlay}
            onChange={(e) => setShowRpmOverlay(e.target.checked)}
          />
          RPM overlay
        </label>

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
  rpmOverlay,
}: {
  resultList: Array<Record<string, unknown>>;
  axis: string;
  sub: boolean;
  rpmOverlay: { freq: number[]; fundamental: number[]; harmonics: number[][] } | null;
}) {
  const plotLayoutBase = usePlotLayoutBase();
  const theme = useAppTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const plotTraces: Plotly.Data[] = [];

  resultList.forEach((file, fi) => {
    const fileColor = FILE_OVERLAY_COLORS[fi % FILE_OVERLAY_COLORS.length];
    const axes = file.axes as Record<string, Record<string, { freq: number[]; spec: number[]; freq_sub?: number[]; spec_sub?: number[] }>>;
    const data = axes?.[axis];
    if (!data) return;
    Object.entries(data).forEach(([trace, spec]) => {
      const freq = sub ? spec.freq_sub || spec.freq : spec.freq;
      const specData = sub ? spec.spec_sub || spec.spec : spec.spec;
      if (!freq?.length) return;
      const mask = sub ? freq.map((f) => f <= 100) : freq.map(() => true);
      plotTraces.push({
        x: freq.filter((_, i) => mask[i]),
        y: specData.filter((_, i) => mask[i]),
        type: 'scatter',
        mode: 'lines',
        name: `${String(file.name)} — ${trace}`,
        line: { color: trace.startsWith('motor_') ? getTraceColor(trace, theme) : fileColor, width: trace.startsWith('motor_') ? 1 : 2 },
      });
    });
  });

  if (rpmOverlay && !sub) {
    rpmOverlay.fundamental.forEach((rpmHz, ti) => {
      if (!rpmHz || rpmHz <= 0) return;
      plotTraces.push({
        x: [rpmHz, rpmHz],
        y: [0, 1],
        yaxis: 'y',
        type: 'scatter',
        mode: 'lines',
        name: `RPM bin ${ti + 1}`,
        line: { color: 'rgba(255, 255, 0, 0.5)', width: 1, dash: 'dash' },
        showlegend: false,
      });
    });
  }

  const handleSave = useCallback(async () => {
    const plotEl = containerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (!plotEl) return;
    await savePlotlyFigure(plotEl, `spectral-${axis}-${sub ? 'sub100' : 'full'}`);
  }, [axis, sub]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        className="absolute top-1 right-1 z-10 btn-run text-[10px] px-2 py-0.5 opacity-70 hover:opacity-100"
        onClick={handleSave}
        title="Save figure as PNG"
      >
        Save
      </button>
      <Plot
        data={plotTraces}
        layout={{
          ...plotLayoutBase,
          title: `${axis.charAt(0).toUpperCase() + axis.slice(1)} | ${sub ? 'Sub 100Hz' : 'Full Spectrum'}`,
          height: 220,
          xaxis: { ...plotLayoutBase.xaxis, title: 'Frequency (Hz)' },
          yaxis: { ...plotLayoutBase.yaxis, title: 'PSD (dB)' },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plot from '../components/Plot';
import { api } from '../lib/api';
import {
  AXIS_LABELS,
  FILE_OVERLAY_COLORS,
  FILE_OVERLAY_LINE_DASHES,
  getTraceColor,
  INTERACTIVE_PLOT_CONFIG,
  TRACE_LABELS,
} from '../lib/constants';
import { savePlotlyFigure } from '../lib/utils';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const SIGNAL_TRACE_OPTIONS = [
  'gyro', 'gyro_pf', 'dterm', 'pterm', 'piderr', 'setpoint',
] as const;

/** Quad motor grid order (matches PIDscope panel layout). */
const MOTOR_GRID: { motorIdx: number; label: string }[][] = [
  [{ motorIdx: 3, label: 'M4' }, { motorIdx: 1, label: 'M2' }],
  [{ motorIdx: 2, label: 'M3' }, { motorIdx: 0, label: 'M1' }],
];

const RPM_NOTCH_OPTIONS = [
  { value: 'off', label: 'RPM Notc off' },
  { value: '1', label: '1st harmonic' },
  { value: '2', label: '2nd harmonic' },
  { value: '3', label: '3rd harmonic' },
  { value: '1,2', label: '1st & 2nd' },
  { value: '1,3', label: '1st & 3rd' },
  { value: '2,3', label: '2nd & 3rd' },
  { value: '1,2,3', label: '1st, 2nd, & 3rd' },
] as const;

const DYN_NOTCH_OPTIONS = [
  { value: 'off', label: 'Dyn Notc off' },
  { value: '1', label: 'DN1' },
  { value: '2', label: 'DN2' },
  { value: '3', label: 'DN3' },
  { value: '4', label: 'DN4' },
  { value: '5', label: 'DN5' },
  { value: '6', label: 'DN6' },
  { value: '7', label: 'DN7' },
  { value: 'all', label: 'All' },
] as const;

const SECONDARY_VIEW_OPTIONS = [
  { value: 'sub100', label: 'sub 100Hz' },
  { value: 'motorNoise', label: 'Motor Noise' },
] as const;

type RpmOverlayCurve = {
  motor: number;
  harmonic: number;
  center_hz?: number;
  freq: number[];
  y: number[];
  color: string;
  dash: string;
};

type DynOverlayCurve = {
  notch: number;
  freq: number[];
  y: number[];
  color: string;
};

type MotorNoiseAxisData = {
  harmonics: number[];
  pre_filt: number[];
  post_filt: number[];
  pre_std: number[];
  post_std: number[];
};

const SPECTRUM_PLOT_HEIGHT = 220;
const SPECTRUM_PLOT_HEIGHT_EXPANDED = 520;
const SPECTRUM_PLOT_HEIGHT_DUAL = 300;
const SPECTRUM_GRID_COLS = '1.25rem 1fr';
const AXIS_TOGGLE_LABELS = ['R', 'P', 'Y'] as const;
const SPECTRUM_X_LABEL = 'Frequency (Hz)';
const SPECTRUM_Y_RANGE_PSD: [number, number] = [-50, 20];
const SPECTRUM_Y_RANGE_AMP: [number, number] = [0, 0.5];

function defaultYRange(psd: boolean): [number, number] {
  return psd ? SPECTRUM_Y_RANGE_PSD : SPECTRUM_Y_RANGE_AMP;
}

const AXIS_KEYS = ['roll', 'pitch', 'yaw'] as const;

function spectrumYLabel(axis: string, psd: boolean): string {
  const idx = AXIS_KEYS.indexOf(axis as (typeof AXIS_KEYS)[number]);
  const channel = idx >= 0 ? AXIS_LABELS[idx] : axis;
  const unit = psd ? 'PSD (dB)' : 'Amplitude';
  return `${channel} — ${unit}`;
}

function spectrumTraceName(
  fileIdx: number,
  traceKey: string,
  multiFile: boolean,
): string {
  const label = TRACE_LABELS[traceKey] || traceKey;
  if (!multiFile) return label;
  return `F${fileIdx + 1} · ${label}`;
}

type SpectrumRunOverrides = {
  smoothFactor?: number;
  rpmNotchMode?: string;
  dynNotchMode?: string;
  rpmEst?: boolean;
  rpmMultiplier?: number;
  secondaryView?: 'sub100' | 'motorNoise';
  rpmMotors?: number[];
};

type OverlayCapabilities = {
  rpm_notch: { available: boolean; message: string };
  dyn_notch: { available: boolean; message: string };
};

const RPM_NOTCH_ENABLED_TITLE = 'RPM notch harmonic overlays (Full Spectrum, PSD on)';
const DYN_NOTCH_ENABLED_TITLE = 'Dynamic notch filter overlays (Full Spectrum, PSD on)';

export function SpectralAnalyzerPage() {
  const theme = useAppTheme();
  const { sessionId, files } = useSessionStore();
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [traces, setTraces] = useState(['gyro', 'gyro_pf']);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([0]);
  const [rpmMotors, setRpmMotors] = useState<[boolean, boolean, boolean, boolean]>([true, true, true, true]);
  const [rpmNotchMode, setRpmNotchMode] = useState('off');
  const [dynNotchMode, setDynNotchMode] = useState('off');
  const [rpmEst, setRpmEst] = useState(false);
  const [rpmMultiplier, setRpmMultiplier] = useState(2.1);
  const [secondaryView, setSecondaryView] = useState<'sub100' | 'motorNoise'>('sub100');
  const [smoothFactor, setSmoothFactor] = useState(1);
  const [axisVisible, setAxisVisible] = useState<[boolean, boolean, boolean]>([true, true, true]);
  const [showPsd, setShowPsd] = useState(true);
  const [yAutoscale, setYAutoscale] = useState(false);
  const [yMin, setYMin] = useState(SPECTRUM_Y_RANGE_PSD[0]);
  const [yMax, setYMax] = useState(SPECTRUM_Y_RANGE_PSD[1]);
  const [overlayCaps, setOverlayCaps] = useState<OverlayCapabilities | null>(null);

  const rpmNotchAvailable = overlayCaps?.rpm_notch.available ?? false;
  const dynNotchAvailable = overlayCaps?.dyn_notch.available ?? false;
  const rpmNotchTitle = rpmNotchAvailable
    ? RPM_NOTCH_ENABLED_TITLE
    : (overlayCaps?.rpm_notch.message ?? 'Load a log file first.');
  const dynNotchTitle = dynNotchAvailable
    ? DYN_NOTCH_ENABLED_TITLE
    : (overlayCaps?.dyn_notch.message ?? 'Load a log file first.');

  useEffect(() => {
    if (!sessionId || selectedFiles.length === 0) {
      setOverlayCaps(null);
      return;
    }
    let cancelled = false;
    void api
      .runOverlayCapabilities({
        session_id: sessionId,
        file_indices: selectedFiles,
        rpm_estimate: rpmEst,
        rpm_multiplier: rpmMultiplier,
      })
      .then((caps) => {
        if (!cancelled) setOverlayCaps(caps);
      })
      .catch(() => {
        if (!cancelled) setOverlayCaps(null);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, selectedFiles, rpmEst, rpmMultiplier]);

  useEffect(() => {
    if (!rpmNotchAvailable && rpmNotchMode !== 'off') {
      setRpmNotchMode('off');
    }
  }, [rpmNotchAvailable, rpmNotchMode]);

  useEffect(() => {
    if (!dynNotchAvailable && dynNotchMode !== 'off') {
      setDynNotchMode('off');
    }
  }, [dynNotchAvailable, dynNotchMode]);

  const toggleTrace = (traceKey: string) => {
    setTraces((tr) => (tr.includes(traceKey) ? tr.filter((x) => x !== traceKey) : [...tr, traceKey]));
  };

  const selectedRpmMotorIndices = useMemo(
    () => rpmMotors.map((on, i) => (on ? i : -1)).filter((i) => i >= 0),
    [rpmMotors],
  );

  const toggleAxis = (idx: number) => {
    setAxisVisible((prev) => {
      const next: [boolean, boolean, boolean] = [...prev] as [boolean, boolean, boolean];
      next[idx] = !next[idx];
      return next.some(Boolean) ? next : prev;
    });
  };

  const visibleAxes = AXIS_KEYS.filter((_, i) => axisVisible[i]);
  const panelHeight =
    visibleAxes.length === 1
      ? SPECTRUM_PLOT_HEIGHT_EXPANDED
      : visibleAxes.length === 2
        ? SPECTRUM_PLOT_HEIGHT_DUAL
        : SPECTRUM_PLOT_HEIGHT;

  const runSpectrumAnalysis = useCallback(
    async (psdMode: boolean, overrides?: SpectrumRunOverrides) => {
      if (!sessionId) return;
      const reqRpmNotchMode = overrides?.rpmNotchMode ?? rpmNotchMode;
      const reqDynNotchMode = overrides?.dynNotchMode ?? dynNotchMode;
      const reqRpmMotors = overrides?.rpmMotors ?? selectedRpmMotorIndices;
      const reqRpmEst = overrides?.rpmEst ?? rpmEst;
      const reqRpmMultiplier = overrides?.rpmMultiplier ?? rpmMultiplier;
      const reqSecondaryView = overrides?.secondaryView ?? secondaryView;
      const reqSmoothFactor = overrides?.smoothFactor ?? smoothFactor;
      setLoading(true);
      try {
        const data = await api.runSpectrum({
          session_id: sessionId,
          file_indices: selectedFiles,
          axes: [0, 1, 2],
          traces,
          psd: psdMode,
          sub100hz: true,
          smooth_factor: reqSmoothFactor,
          rpm_notch_mode: reqRpmNotchMode,
          dyn_notch_mode: reqDynNotchMode,
          rpm_motors: reqRpmMotors,
          rpm_estimate: reqRpmEst,
          rpm_multiplier: reqRpmMultiplier,
          include_motor_noise: reqSecondaryView === 'motorNoise',
        });
        setResults(data.results);
      } finally {
        setLoading(false);
      }
    },
    [
      sessionId,
      selectedFiles,
      traces,
      smoothFactor,
      rpmNotchMode,
      dynNotchMode,
      selectedRpmMotorIndices,
      rpmEst,
      rpmMultiplier,
      secondaryView,
    ],
  );

  const run = () => runSpectrumAnalysis(showPsd);

  const handlePsdToggle = (checked: boolean) => {
    setShowPsd(checked);
    setYAutoscale(true);
    const [ymin, ymax] = defaultYRange(checked);
    setYMin(ymin);
    setYMax(ymax);
    if (results.length > 0) {
      void runSpectrumAnalysis(checked, { smoothFactor });
    }
  };

  const handleYLimitChange = (which: 'min' | 'max', raw: string) => {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    setYAutoscale(false);
    if (which === 'min') setYMin(value);
    else setYMax(value);
  };

  const handleSmoothChange = (next: number) => {
    setSmoothFactor(next);
    if (results.length > 0 && sessionId) {
      void runSpectrumAnalysis(showPsd, { smoothFactor: next });
    }
  };

  const rerunIfReady = (overrides?: SpectrumRunOverrides) => {
    if (results.length > 0 && sessionId) {
      void runSpectrumAnalysis(showPsd, overrides);
    }
  };

  const toggleRpmMotor = (idx: number) => {
    const next: [boolean, boolean, boolean, boolean] = [...rpmMotors] as [
      boolean,
      boolean,
      boolean,
      boolean,
    ];
    next[idx] = !next[idx];
    if (!next.some(Boolean)) return;
    setRpmMotors(next);
    const nextIndices = next.map((on, i) => (on ? i : -1)).filter((i) => i >= 0);
    rerunIfReady({ rpmMotors: nextIndices });
  };

  const resultList = results;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div
        className="flex-1 grid grid-cols-2 gap-2 min-h-0 overflow-y-auto"
        style={{ gridTemplateRows: `repeat(${visibleAxes.length}, minmax(0, auto))` }}
      >
        {visibleAxes.flatMap((axis) => [
          <SpectrumPanel
            key={`${axis}-full`}
            resultList={resultList}
            axis={axis}
            sub={false}
            plotHeight={panelHeight}
            psd={showPsd}
            yAutoscale={yAutoscale}
            yMin={yMin}
            yMax={yMax}
            smoothFactor={smoothFactor}
            showOverlays={showPsd}
          />,
          secondaryView === 'sub100' ? (
            <SpectrumPanel
              key={`${axis}-sub`}
              resultList={resultList}
              axis={axis}
              sub={true}
              plotHeight={panelHeight}
              psd={showPsd}
              yAutoscale={yAutoscale}
              yMin={yMin}
              yMax={yMax}
              smoothFactor={smoothFactor}
              showOverlays={false}
            />
          ) : (
            <MotorNoisePanel
              key={`${axis}-mn`}
              resultList={resultList}
              axis={axis}
              plotHeight={panelHeight}
            />
          ),
        ])}
      </div>

      <div className="panel w-56 flex flex-col gap-2 shrink-0 min-h-0">
        <div className="flex flex-col gap-2 min-h-0 flex-1 overflow-y-auto">
          <div className="rounded border border-[var(--border)] bg-[var(--bg-secondary)] p-2 space-y-1">
            <div className="text-xs font-semibold">select files (max 10)</div>
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
                  {f.original_name.slice(0, 22)}
                </span>
              </label>
            ))}
          </div>

          <div className="rounded border border-[var(--border)] bg-[var(--bg-secondary)] p-2 space-y-1">
            {SIGNAL_TRACE_OPTIONS.map((t) => (
              <label key={t} className="flex gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={traces.includes(t)}
                  onChange={() => toggleTrace(t)}
                />
                <span style={{ color: getTraceColor(t, theme) }}>{TRACE_LABELS[t] || t}</span>
              </label>
            ))}
          </div>

          <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
            {loading ? 'Running...' : 'Run'}
          </button>

          <select
            className="select-input"
            value={smoothFactor}
            onChange={(e) => handleSmoothChange(Number(e.target.value))}
          >
            <option value={0}>smooth off</option>
            <option value={1}>smoothing low</option>
            <option value={2}>smoothing low-med</option>
            <option value={3}>smoothing medium</option>
            <option value={4}>smoothing med-high</option>
            <option value={5}>smoothing high</option>
          </select>
        </div>

        <div className="shrink-0 space-y-2 border-t border-[var(--border)] pt-2">
          <div className="flex gap-3">
            {AXIS_TOGGLE_LABELS.map((label, i) => (
              <label key={label} className="text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={axisVisible[i]}
                  onChange={() => toggleAxis(i)}
                />{' '}
                {label}
              </label>
            ))}
          </div>

          <label className="flex gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={showPsd}
              onChange={(e) => handlePsdToggle(e.target.checked)}
            />
            PSD
          </label>

          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs">
              <span className="block text-center mb-0.5 text-[var(--text-secondary)]">Y min</span>
              <input
                type="number"
                className="select-input w-full text-center px-1"
                value={yMin}
                step={showPsd ? 1 : 0.01}
                onChange={(e) => handleYLimitChange('min', e.target.value)}
              />
            </label>
            <label className="text-xs">
              <span className="block text-center mb-0.5 text-[var(--text-secondary)]">Y max</span>
              <input
                type="number"
                className="select-input w-full text-center px-1"
                value={yMax}
                step={showPsd ? 1 : 0.01}
                onChange={(e) => handleYLimitChange('max', e.target.value)}
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <select
              className="select-input text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              title={rpmNotchTitle}
              disabled={!rpmNotchAvailable}
              value={rpmNotchMode}
              onChange={(e) => {
                const next = e.target.value;
                setRpmNotchMode(next);
                rerunIfReady({ rpmNotchMode: next });
              }}
            >
              {RPM_NOTCH_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              className="select-input text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              title={dynNotchTitle}
              disabled={!dynNotchAvailable}
              value={dynNotchMode}
              onChange={(e) => {
                const next = e.target.value;
                setDynNotchMode(next);
                rerunIfReady({ dynNotchMode: next });
              }}
            >
              {DYN_NOTCH_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            {MOTOR_GRID.flat().map(({ motorIdx, label }) => (
              <label key={motorIdx} className="flex gap-1.5 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={rpmMotors[motorIdx]}
                  onChange={() => toggleRpmMotor(motorIdx)}
                />
                <span style={{ color: getTraceColor(`motor_${motorIdx}`, theme) }}>{label}</span>
              </label>
            ))}
          </div>

          <select
            className="select-input text-xs"
            value={secondaryView}
            onChange={(e) => {
              const next = e.target.value as 'sub100' | 'motorNoise';
              setSecondaryView(next);
              if (results.length > 0 && sessionId) {
                void runSpectrumAnalysis(showPsd, { secondaryView: next });
              }
            }}
          >
            {SECONDARY_VIEW_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs text-[var(--text-secondary)]">multiplier</span>
            <input
              type="number"
              className="select-input w-14 text-center px-1 text-xs"
              value={rpmMultiplier}
              step={0.1}
              min={0.1}
              onChange={(e) => {
                const next = Number(e.target.value) || 2.1;
                setRpmMultiplier(next);
                if (rpmEst) {
                  rerunIfReady({ rpmMultiplier: next });
                }
              }}
            />
            <label className="flex gap-1.5 items-center ml-auto">
              <input
                type="checkbox"
                checked={rpmEst}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setRpmEst(checked);
                  rerunIfReady({ rpmEst: checked });
                }}
              />
              RPM est.
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

function SpectrumPanel({
  resultList,
  axis,
  sub,
  plotHeight,
  psd,
  yAutoscale,
  yMin,
  yMax,
  smoothFactor,
  showOverlays,
}: {
  resultList: Array<Record<string, unknown>>;
  axis: string;
  sub: boolean;
  plotHeight: number;
  psd: boolean;
  yAutoscale: boolean;
  yMin: number;
  yMax: number;
  smoothFactor: number;
  showOverlays: boolean;
}) {
  const plotLayoutBase = usePlotLayoutBase();
  const theme = useAppTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const plotTraces: Plotly.Data[] = [];
  const multiFile = resultList.length > 1;
  let dataTraceCount = 0;

  resultList.forEach((file) => {
    const fileIdx = Number(file.file_idx ?? 0);
    const fileName = String(file.name ?? '');
    const axes = file.axes as Record<string, Record<string, { freq: number[]; spec: number[]; freq_sub?: number[]; spec_sub?: number[] }>>;
    const data = axes?.[axis];
    if (!data) return;
    Object.entries(data).forEach(([trace, spec]) => {
      const freq = sub ? spec.freq_sub || spec.freq : spec.freq;
      const specData = sub ? spec.spec_sub || spec.spec : spec.spec;
      if (!freq?.length) return;
      dataTraceCount += 1;
      const mask = sub ? freq.map((f) => f <= 100) : freq.map(() => true);
      const traceLabel = TRACE_LABELS[trace] || trace;
      const fullName = multiFile ? `${fileName} — ${traceLabel}` : traceLabel;
      plotTraces.push({
        x: freq.filter((_, i) => mask[i]),
        y: specData.filter((_, i) => mask[i]),
        type: 'scatter',
        mode: 'lines',
        name: spectrumTraceName(fileIdx, trace, multiFile),
        hovertemplate: psd
          ? `%{x:.1f} Hz<br>%{y:.1f} dB<br>${fullName}<extra></extra>`
          : `%{x:.1f} Hz<br>%{y:.4f}<br>${fullName}<extra></extra>`,
        line: {
          color: getTraceColor(trace, theme),
          dash: multiFile
            ? FILE_OVERLAY_LINE_DASHES[fileIdx % FILE_OVERLAY_LINE_DASHES.length]
            : 'solid',
          width: trace.startsWith('motor_') ? 1 : 2,
        },
      });
    });
  });

  if (showOverlays && !sub && psd) {
    let freqMax = 1000;
    plotTraces.forEach((t) => {
      const scatter = t as Plotly.ScatterData;
      if (Array.isArray(scatter.x)) {
        const xs = scatter.x.filter((v): v is number => typeof v === 'number');
        if (xs.length) {
          const localMax = Math.max(...xs);
          if (localMax > freqMax) freqMax = localMax;
        }
      }
    });
    resultList.forEach((file) => {
      const rpmCurves = (file.rpm_overlays as RpmOverlayCurve[] | undefined) ?? [];
      const dynCurves = (file.dyn_overlays as DynOverlayCurve[] | undefined) ?? [];
      rpmCurves.forEach((curve) => {
        const mask = curve.freq.map((f) => f <= freqMax);
        plotTraces.push({
          x: curve.freq.filter((_, i) => mask[i]),
          y: curve.y.filter((_, i) => mask[i]),
          type: 'scatter',
          mode: 'lines',
          name: `M${curve.motor + 1} H${curve.harmonic}`,
          line: { color: curve.color, width: 1.2, dash: curve.dash as Plotly.Dash },
          showlegend: false,
          hoverinfo: 'skip',
        });
      });
      dynCurves.forEach((curve) => {
        const mask = curve.freq.map((f) => f <= freqMax);
        plotTraces.push({
          x: curve.freq.filter((_, i) => mask[i]),
          y: curve.y.filter((_, i) => mask[i]),
          type: 'scatter',
          mode: 'lines',
          name: `DN${curve.notch}`,
          line: { color: curve.color, width: 1 },
          showlegend: false,
          hoverinfo: 'skip',
        });
      });
    });
  }

  const handleSave = useCallback(async () => {
    const plotEl = containerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (!plotEl) return;
    await savePlotlyFigure(plotEl, `spectral-${axis}-${sub ? 'sub100' : 'full'}`);
  }, [axis, sub]);

  const panelTitle = `${axis.charAt(0).toUpperCase() + axis.slice(1)} | ${sub ? 'Sub 100Hz' : 'Full Spectrum'}`;
  const showLegend = dataTraceCount > 1;

  return (
    <div
      ref={containerRef}
      className="grid gap-x-1 min-w-0"
      style={{ gridTemplateColumns: SPECTRUM_GRID_COLS }}
    >
      <div
        className="flex items-center justify-center self-stretch text-xs text-[var(--text-secondary)]"
        aria-hidden
      >
        <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap text-center">
          {spectrumYLabel(axis, psd)}
        </span>
      </div>
      <div className="relative min-w-0">
        <button
          type="button"
          className="absolute top-1 left-1 z-10 btn-run text-[10px] px-2 py-0.5 opacity-70 hover:opacity-100"
          onClick={handleSave}
          title="Save figure as PNG"
        >
          Save
        </button>
        <Plot
          key={`${axis}-${sub ? 'sub' : 'full'}-${psd ? 'psd' : 'amp'}-s${smoothFactor}-${yAutoscale ? 'auto' : `${yMin}-${yMax}`}`}
          data={plotTraces}
          layout={{
            ...plotLayoutBase,
            title: panelTitle,
            height: plotHeight,
            margin: {
              ...plotLayoutBase.margin,
              t: showLegend ? 56 : 30,
              l: 42,
              r: 10,
              b: 28,
            },
            showlegend: showLegend,
            legend: showLegend
              ? {
                  orientation: 'h',
                  y: 1.18,
                  x: 0,
                  xanchor: 'left',
                  font: { size: 9 },
                }
              : undefined,
            xaxis: { ...plotLayoutBase.xaxis, title: '' },
            yaxis: {
              ...plotLayoutBase.yaxis,
              title: '',
              ...(yAutoscale
                ? { autorange: true, fixedrange: false }
                : { range: [yMin, yMax] as [number, number] }),
            },
          }}
          config={INTERACTIVE_PLOT_CONFIG}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </div>
      <div aria-hidden />
      <p className="text-xs text-center text-[var(--text-secondary)]">{SPECTRUM_X_LABEL}</p>
    </div>
  );
}

function MotorNoisePanel({
  resultList,
  axis,
  plotHeight,
}: {
  resultList: Array<Record<string, unknown>>;
  axis: string;
  plotHeight: number;
}) {
  const plotLayoutBase = usePlotLayoutBase();
  const theme = useAppTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const axisIdx = AXIS_KEYS.indexOf(axis as (typeof AXIS_KEYS)[number]);
  const channel = axisIdx >= 0 ? AXIS_LABELS[axisIdx] : axis;

  const file = resultList[0];
  const mn = (file?.motor_noise as Record<string, MotorNoiseAxisData> | undefined)?.[axis];
  const plotTraces: Plotly.Data[] = [];
  const harmLabels = ['1st', '2nd', '3rd'];
  const traceColor = getTraceColor('gyro', theme);

  if (mn?.harmonics?.length) {
    plotTraces.push({
      x: harmLabels,
      y: mn.pre_filt,
      error_y: { type: 'data', array: mn.pre_std, visible: true, color: traceColor },
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Pre-filter',
      line: { color: traceColor, dash: 'dot', width: 2 },
      marker: { color: traceColor, size: 6 },
    });
    plotTraces.push({
      x: harmLabels,
      y: mn.post_filt,
      error_y: { type: 'data', array: mn.post_std, visible: true, color: traceColor },
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Post-filter',
      line: { color: traceColor, width: 2 },
      marker: { color: traceColor, size: 6 },
    });
  }

  const handleSave = useCallback(async () => {
    const plotEl = containerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (!plotEl) return;
    await savePlotlyFigure(plotEl, `motor-noise-${axis}`);
  }, [axis]);

  return (
    <div
      ref={containerRef}
      className="grid gap-x-1 min-w-0"
      style={{ gridTemplateColumns: SPECTRUM_GRID_COLS }}
    >
      <div
        className="flex items-center justify-center self-stretch text-xs text-[var(--text-secondary)]"
        aria-hidden
      >
        <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap text-center">
          {channel} — Avg Motor Noise (dB)
        </span>
      </div>
      <div className="relative min-w-0">
        <button
          type="button"
          className="absolute top-1 left-1 z-10 btn-run text-[10px] px-2 py-0.5 opacity-70 hover:opacity-100"
          onClick={handleSave}
          title="Save figure as PNG"
        >
          Save
        </button>
        <Plot
          data={plotTraces}
          layout={{
            ...plotLayoutBase,
            title: `${axis.charAt(0).toUpperCase() + axis.slice(1)} | Motor Noise`,
            height: plotHeight,
            margin: { ...plotLayoutBase.margin, t: 30, l: 42, r: 10, b: 36 },
            showlegend: plotTraces.length > 1,
            legend: { orientation: 'h', y: 1.12, x: 0, font: { size: 9 } },
            xaxis: { ...plotLayoutBase.xaxis, title: '' },
            yaxis: { ...plotLayoutBase.yaxis, title: '', range: [-50, 20] },
          }}
          config={INTERACTIVE_PLOT_CONFIG}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </div>
      <div aria-hidden />
      <p className="text-xs text-center text-[var(--text-secondary)]">Motor Harmonic</p>
    </div>
  );
}

import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import Plot from '../components/Plot';
import { EpochRangeSlider } from '../components/EpochRangeSlider';
import {
  api,
  type SysIdModel,
  type SysIdPreviewFlight,
  type SysIdPreviewResult,
  type SysIdRunResult,
} from '../lib/api';
import { PREVIEW_PLOT_CONFIG, RESULT_PLOT_CONFIG } from '../lib/constants';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

const MAX_PLOT_POINTS = 2500;

function downsampleIndices(length: number, maxPoints: number): number[] {
  if (length <= maxPoints) return Array.from({ length }, (_, i) => i);
  const indices: number[] = [];
  const step = (length - 1) / (maxPoints - 1);
  for (let i = 0; i < maxPoints; i++) {
    indices.push(Math.round(i * step));
  }
  return indices;
}

function downsampleXY(x: number[], y: number[], maxPoints = MAX_PLOT_POINTS) {
  const indices = downsampleIndices(x.length, maxPoints);
  return {
    x: indices.map((i) => x[i]),
    y: indices.map((i) => y[i]),
  };
}

const DEFAULT_MODEL: SysIdModel = {
  mass: 1.0,
  gravity: 9.81,
  inertia_ratio: 1.832,
  rotor_positions: [
    [0.15, -0.15, 0],
    [-0.15, 0.15, 0],
    [0.15, 0.15, 0],
    [-0.15, -0.15, 0],
  ],
  rotor_thrust_directions: [
    [0, 0, 1],
    [0, 0, 1],
    [0, 0, 1],
    [0, 0, 1],
  ],
  rotor_torque_directions: [
    [0, 0, -1],
    [0, 0, -1],
    [0, 0, 1],
    [0, 0, 1],
  ],
};

type PhaseKey = 'thrust' | 'inertia_rp' | 'inertia_yaw';

type FileRange = { start: number; end: number };

/** Per-phase, per-file slider positions (file index → start/end). */
type PhaseRangesByFile = Record<PhaseKey, Record<number, FileRange>>;

/** Per-phase, per-file inclusion in estimation. */
type PhaseEnabledByFile = Record<PhaseKey, Record<number, boolean>>;

const PHASE_KEYS: PhaseKey[] = ['thrust', 'inertia_rp', 'inertia_yaw'];

const PHASE_LABELS: Record<PhaseKey, string> = {
  thrust: 'Thrust / motor model',
  inertia_rp: 'Roll & pitch inertia',
  inertia_yaw: 'Yaw torque (Kτ)',
};

type MetricKey = 'thrust_z' | 'torque_x' | 'torque_y' | 'torque_z';

const PHASE_METRICS: Record<PhaseKey, Array<{ key: MetricKey; name: string; color: string }>> = {
  thrust: [
    { key: 'thrust_z', name: 'Thrust Z', color: '#66ff66' },
    { key: 'torque_x', name: 'Torque X', color: '#ff66aa' },
    { key: 'torque_y', name: 'Torque Y', color: '#aaaaff' },
    { key: 'torque_z', name: 'Torque Z', color: '#ffff66' },
  ],
  inertia_rp: [
    { key: 'torque_x', name: 'Torque roll (X)', color: '#ff66aa' },
    { key: 'torque_y', name: 'Torque pitch (Y)', color: '#aaaaff' },
  ],
  inertia_yaw: [{ key: 'torque_z', name: 'Torque yaw (Z)', color: '#ffff66' }],
};

function sliceByTime(timestamps: number[], values: number[], start: number, end: number) {
  const x: number[] = [];
  const y: number[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const t = timestamps[i];
    if (t >= start && t <= end) {
      x.push(t);
      y.push(values[i]);
    }
  }
  return { x, y };
}

function buildPhaseTraces(
  flight: SysIdPreviewFlight | null,
  phase: PhaseKey,
  start: number,
  end: number,
): Plotly.Data[] {
  if (!flight) return [];
  const m = flight.metrics;
  return PHASE_METRICS[phase].map(({ key, name, color }) => {
    const series = m[key];
    const sliced = sliceByTime(series.timestamps, series.values, start, end);
    const { x, y } = downsampleXY(sliced.x, sliced.y);
    return {
      x,
      y,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name,
      line: { color, width: 1.5 },
    };
  });
}

const RESULT_PLOT_HEIGHT = 220;
const RESULT_PLOT_MARGIN = { l: 52, r: 16, t: 28, b: 44 };

function ResultPlot({
  title,
  traces,
  layout,
  plotLayoutBase,
}: {
  title: string;
  traces: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  plotLayoutBase: ReturnType<typeof usePlotLayoutBase>;
}) {
  return (
    <div>
      <h4 className="text-xs text-[var(--text-secondary)] mb-1">{title}</h4>
      <Plot
        data={traces}
        layout={{
          ...plotLayoutBase,
          ...layout,
          height: RESULT_PLOT_HEIGHT,
          margin: RESULT_PLOT_MARGIN,
          uirevision: title,
        }}
        config={RESULT_PLOT_CONFIG}
        className="w-full"
      />
    </div>
  );
}

const SysIdResultPlots = memo(function SysIdResultPlots({ result }: { result: SysIdRunResult }) {
  const plotLayoutBase = usePlotLayoutBase();
  const p = result.plots;
  const tau = p.tau_curve as
    | { t_m_candidates: number[]; rmses: number[]; t_m: number }
    | undefined;
  const fit = p.thrust_fit as { predicted: number[]; actual: number[] } | undefined;
  const hover = p.hover_hist as
    | {
        rpms: number[];
        median_rpm: number;
        predicted_hover_rpm: number;
        hover_percentile?: number;
      }
    | undefined;
  const thrustVsOmegaSq = p.thrust_vs_rpm as
    | {
        omega_sq: number[];
        thrust: number[];
        fit_quad: { d: number; x: number[]; y: number[] };
      }
    | undefined;
  const inertia = p.inertia as Record<
    string,
    {
      torque_fit: number[];
      dw_fit: number[];
      fit_line_x: number[];
      fit_line_y: number[];
      i_axis: number;
    }
  >;
  const yaw = p.yaw as {
    thrust_torque_z: number[];
    b: number[];
    fit_line_x: number[];
    fit_line_y: number[];
    k_tau: number;
  };

  const tauPlot =
    tau &&
    (() => {
      const rmseMin = Math.min(...tau.rmses);
      const rmseMax = Math.max(...tau.rmses);
      return (
        <ResultPlot
          title="Motor time constant Tm"
          plotLayoutBase={plotLayoutBase}
          traces={[
            { x: tau.t_m_candidates, y: tau.rmses, type: 'scatter', mode: 'lines', name: 'RMSE' },
            {
              x: [tau.t_m, tau.t_m],
              y: [rmseMin, rmseMax],
              type: 'scatter',
              mode: 'lines',
              name: `Tm=${tau.t_m.toFixed(3)} s`,
              line: { dash: 'dash', color: 'red' },
            },
          ]}
          layout={{
            xaxis: { title: { text: 'Tm [s]' } },
            yaxis: { title: { text: 'RMSE' } },
          }}
        />
      );
    })();

  const thrustOmegaSqPlot =
    thrustVsOmegaSq?.fit_quad?.x?.length &&
    (() => {
      const scatter = downsampleXY(thrustVsOmegaSq.omega_sq, thrustVsOmegaSq.thrust);
      return (
        <ResultPlot
          title="Thrust vs ω²"
          plotLayoutBase={plotLayoutBase}
          traces={[
            {
              x: scatter.x,
              y: scatter.y,
              type: 'scatter',
              mode: 'markers',
              marker: { size: 2, opacity: 0.35 },
              name: 'data',
            },
            {
              x: thrustVsOmegaSq.fit_quad.x,
              y: thrustVsOmegaSq.fit_quad.y,
              type: 'scatter',
              mode: 'lines',
              name: `T = d·ω² (d=${thrustVsOmegaSq.fit_quad.d.toFixed(6)})`,
              line: { color: '#00cccc', width: 2 },
            },
          ]}
          layout={{
            xaxis: { title: { text: 'ω₁² + ω₂² + ω₃² + ω₄²' } },
            yaxis: { title: { text: 'Thrust [N]' } },
            showlegend: true,
            legend: { orientation: 'h', y: 1.18, font: { size: 9 } },
          }}
        />
      );
    })();

  const fitPlot =
    fit &&
    (() => {
      const scatter = downsampleXY(fit.predicted, fit.actual);
      const minV = Math.min(...fit.predicted, ...fit.actual);
      const maxV = Math.max(...fit.predicted, ...fit.actual);
      return (
        <ResultPlot
          title="Thrust fit"
          plotLayoutBase={plotLayoutBase}
          traces={[
            {
              x: scatter.x,
              y: scatter.y,
              type: 'scatter',
              mode: 'markers',
              marker: { size: 2, opacity: 0.4 },
              name: 'samples',
            },
            {
              x: [minV, maxV],
              y: [minV, maxV],
              type: 'scatter',
              mode: 'lines',
              name: 'identity',
              line: { color: 'red' },
            },
          ]}
          layout={{
            xaxis: { title: { text: 'Predicted thrust [N]' } },
            yaxis: { title: { text: 'Actual thrust [N]' } },
          }}
        />
      );
    })();

  const hoverPlot =
    hover?.rpms?.length &&
    (() => (
        <ResultPlot
          title="Hovering throttle"
          plotLayoutBase={plotLayoutBase}
          traces={[
            {
              x: hover.rpms,
              type: 'histogram',
              xbins: { size: (Math.max(...hover.rpms) - Math.min(...hover.rpms)) / 50 || 0.01 },
              marker: { color: '#4a90d9' },
              name: 'Count',
              opacity: 0.85,
            } as Plotly.Data,
            {
              x: [null],
              y: [null],
              type: 'scatter',
              mode: 'lines',
              name: `Median: ${hover.median_rpm.toFixed(2)}`,
              line: { color: 'red', dash: 'dash', width: 3 },
            },
            {
              x: [null],
              y: [null],
              type: 'scatter',
              mode: 'lines',
              name: `Predicted: ${hover.predicted_hover_rpm.toFixed(2)}`,
              line: { color: '#e6b800', width: 2 },
            },
          ]}
          layout={{
            xaxis: {
              title: {
                text: `Hovering throttle (${Math.round(hover.hover_percentile ?? 5)}% percentile around 0 acceleration)`,
              },
            },
            yaxis: { title: { text: 'Count' } },
            shapes: [
              {
                type: 'line',
                xref: 'x',
                yref: 'paper',
                x0: hover.median_rpm,
                x1: hover.median_rpm,
                y0: 0,
                y1: 1,
                line: { color: 'red', dash: 'dash', width: 3 },
              },
              {
                type: 'line',
                xref: 'x',
                yref: 'paper',
                x0: hover.predicted_hover_rpm,
                x1: hover.predicted_hover_rpm,
                y0: 0,
                y1: 1,
                line: { color: '#e6b800', width: 2 },
              },
            ],
            showlegend: true,
            legend: { orientation: 'h', y: 1.15 },
          }}
        />
    ))();

  const inertiaPlot = (axis: 'x' | 'y') => {
    const s = inertia?.[axis];
    if (!s) return null;
    const label = axis === 'x' ? 'xx' : 'yy';
    const scatter = downsampleXY(s.torque_fit, s.dw_fit);
    return (
      <ResultPlot
        title={`Inertia I${label}`}
        plotLayoutBase={plotLayoutBase}
        traces={[
          {
            x: scatter.x,
            y: scatter.y,
            type: 'scatter',
            mode: 'markers',
            marker: { size: 2, opacity: 0.4 },
            name: 'samples',
          },
          {
            x: s.fit_line_x,
            y: s.fit_line_y,
            type: 'scatter',
            mode: 'lines',
            name: `I${label}=${s.i_axis.toExponential(3)}`,
            line: { color: 'red' },
          },
        ]}
        layout={{
          xaxis: { title: { text: `Estimated torque (${axis}) [Nm]` } },
          yaxis: { title: { text: `dω/dt ${axis} [rad/s²]` } },
        }}
      />
    );
  };

  const yawPlot =
    yaw &&
    (() => {
      const scatter = downsampleXY(yaw.thrust_torque_z, yaw.b);
      return (
        <ResultPlot
          title="Yaw torque coefficient Kτ"
          plotLayoutBase={plotLayoutBase}
          traces={[
            {
              x: scatter.x,
              y: scatter.y,
              type: 'scatter',
              mode: 'markers',
              marker: { size: 2, opacity: 0.4 },
              name: 'samples',
            },
            {
              x: yaw.fit_line_x,
              y: yaw.fit_line_y,
              type: 'scatter',
              mode: 'lines',
              name: `Kτ=${yaw.k_tau.toExponential(3)}`,
              line: { color: 'red' },
            },
          ]}
          layout={{
            xaxis: { title: { text: 'Normalized torque [Nm]' } },
            yaxis: { title: { text: 'dωz × Izz' } },
          }}
        />
      );
    })();

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {tauPlot}
        {thrustOmegaSqPlot}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {fitPlot}
        {hoverPlot}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {inertiaPlot('x')}
        {inertiaPlot('y')}
      </div>
      {yawPlot && <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{yawPlot}</div>}
    </div>
  );
});

const SYSID_REFERENCE =
  'Data-Driven System Identification of Quadrotors Subject to Motor Delays';

function EstimationSummary({ result }: { result: SysIdRunResult }) {
  const p = result.parameters;
  const hover = result.plots.hover_hist as
    | {
        median_rpm: number;
        median_omega_sq?: number;
        predicted_omega_sq?: number;
        hover_percentile?: number;
      }
    | undefined;
  const d = (result.plots.thrust_vs_rpm as { fit_quad?: { d: number } } | undefined)?.fit_quad?.d;
  const g = 9.81;
  const hoverThrustN = p.mass * g;
  const thrustAtMedianOmegaSq =
    d != null && hover?.median_omega_sq != null ? d * hover.median_omega_sq : null;

  const row = (label: string, value: string) => (
    <div className="flex justify-between gap-2 text-xs">
      <span className="text-[var(--text-secondary)] shrink-0">{label}</span>
      <span className="font-mono text-right break-all">{value}</span>
    </div>
  );

  return (
    <div
      className="border rounded p-2 space-y-2"
      style={{ borderColor: 'var(--border)', background: 'var(--bg-primary)' }}
    >
      <h3 className="text-xs font-medium">Estimated parameters</h3>
      <div className="space-y-1.5">
        <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">Motor / thrust</div>
        {row('Tm', `${p.t_m.toFixed(4)} s`)}
        {row('Thrust RMSE', p.thrust_rmse.toFixed(4))}
        {d != null && row('d (T = d·Σωᵢ²)', d.toFixed(6))}
      </div>
      {hover && (
        <div className="space-y-1.5 border-t border-white/5 pt-2">
          <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">
            Hover ({Math.round(hover.hover_percentile ?? 5)}% accel window)
          </div>
          {row('Hover thrust (mg)', `${hoverThrustN.toFixed(2)} N`)}
          {hover.median_omega_sq != null &&
            row('Median Σωᵢ²', hover.median_omega_sq.toFixed(4))}
          {thrustAtMedianOmegaSq != null &&
            row('Thrust at median Σωᵢ²', `${thrustAtMedianOmegaSq.toFixed(2)} N`)}
          {hover.predicted_omega_sq != null &&
            hover.predicted_omega_sq > 0 &&
            row('Predicted Σωᵢ² (d fit)', hover.predicted_omega_sq.toFixed(4))}
          {row('Median motor ω (hover hist.)', hover.median_rpm.toFixed(2))}
        </div>
      )}
      <div className="space-y-1.5 border-t border-white/5 pt-2">
        <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">Inertia</div>
        {row('Ixx', `${p.i_xx.toExponential(4)} kg·m²`)}
        {row('Iyy', `${p.i_yy.toExponential(4)} kg·m²`)}
        {row('Izz', `${p.i_zz.toExponential(4)} kg·m²`)}
        {row('Izz/Ixx', p.i_xx !== 0 ? (p.i_zz / p.i_xx).toFixed(3) : '—')}
      </div>
      <div className="space-y-1.5 border-t border-white/5 pt-2">
        <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">Yaw</div>
        {row('Kτ', p.k_tau.toExponential(4))}
      </div>
      <div className="space-y-1.5 border-t border-white/5 pt-2">
        <div className="text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">Model inputs</div>
        {row('Mass', `${p.mass.toFixed(3)} kg`)}
        {row('Inertia ratio', (p.inertia_ratio ?? 1.832).toFixed(3))}
      </div>
      <p className="text-[10px] text-[var(--text-secondary)] leading-snug pt-2 border-t border-white/5">
        Reference: <span className="italic">{SYSID_REFERENCE}</span>
      </p>
    </div>
  );
}

function emptyPhaseRanges(): PhaseRangesByFile {
  return { thrust: {}, inertia_rp: {}, inertia_yaw: {} };
}

function emptyPhaseEnabled(): PhaseEnabledByFile {
  return { thrust: {}, inertia_rp: {}, inertia_yaw: {} };
}

function initPhaseEnabledFromPreview(
  prev: PhaseEnabledByFile,
  fileCount: number,
): PhaseEnabledByFile {
  const next: PhaseEnabledByFile = {
    thrust: { ...prev.thrust },
    inertia_rp: { ...prev.inertia_rp },
    inertia_yaw: { ...prev.inertia_yaw },
  };
  for (let fi = 0; fi < fileCount; fi++) {
    for (const phase of PHASE_KEYS) {
      if (!(fi in next[phase])) {
        next[phase][fi] = true;
      }
    }
  }
  return next;
}

function isFileEnabledForPhase(
  enabled: PhaseEnabledByFile,
  phase: PhaseKey,
  fileIdx: number,
): boolean {
  return enabled[phase][fileIdx] !== false;
}

function fullRangeForFlight(flight: SysIdPreviewFlight | null | undefined): FileRange {
  const [t0, t1] = flight?.time_range ?? [0, 10];
  return { start: t0, end: t1 };
}

function initPhaseRangesFromPreview(
  prev: PhaseRangesByFile,
  flights: SysIdPreviewFlight[],
): PhaseRangesByFile {
  const next: PhaseRangesByFile = {
    thrust: { ...prev.thrust },
    inertia_rp: { ...prev.inertia_rp },
    inertia_yaw: { ...prev.inertia_yaw },
  };
  for (let fi = 0; fi < flights.length; fi++) {
    const full = fullRangeForFlight(flights[fi]);
    for (const phase of PHASE_KEYS) {
      if (!(fi in next[phase])) {
        next[phase][fi] = full;
      } else {
        const [t0, t1] = flights[fi]?.time_range ?? [0, 10];
        const r = next[phase][fi];
        const start = Math.max(t0, Math.min(r.start, t1));
        let end = Math.max(t0, Math.min(r.end, t1));
        if (end - start < 0.1) {
          next[phase][fi] = full;
        } else {
          next[phase][fi] = { start, end };
        }
      }
    }
  }
  return next;
}

function Vec3Input({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number[];
  onChange: (v: number[]) => void;
}) {
  return (
    <div className="grid grid-cols-[3rem_1fr_1fr_1fr] gap-1.5 items-center text-xs">
      <span className="text-[var(--text-secondary)]">{label}</span>
      {[0, 1, 2].map((axis) => (
        <input
          key={axis}
          type="number"
          step="0.001"
          className="min-w-0 w-full px-1.5 py-0.5 rounded bg-black/30 border border-white/10"
          value={value[axis] ?? 0}
          onChange={(e) => {
            const next = [...value];
            next[axis] = parseFloat(e.target.value) || 0;
            onChange(next);
          }}
        />
      ))}
    </div>
  );
}

export function SysIdPage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, files, selectedFileIdx } = useSessionStore();
  const [model, setModel] = useState<SysIdModel>(DEFAULT_MODEL);
  const [geometryFileIdx, setGeometryFileIdx] = useState(0);
  const [preview, setPreview] = useState<SysIdPreviewResult | null>(null);
  const [result, setResult] = useState<SysIdRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capWarnings, setCapWarnings] = useState<string[]>([]);

  const [phaseFileIdx, setPhaseFileIdx] = useState<Record<PhaseKey, number>>({
    thrust: 0,
    inertia_rp: 0,
    inertia_yaw: 0,
  });
  const [phaseRanges, setPhaseRanges] = useState<PhaseRangesByFile>(emptyPhaseRanges);
  const [phaseEnabled, setPhaseEnabled] = useState<PhaseEnabledByFile>(emptyPhaseEnabled);

  const getPreviewFlight = useCallback(
    (fileIdx: number): SysIdPreviewFlight | null => {
      if (!preview?.flights.length) return null;
      if (preview.flights[fileIdx]) return preview.flights[fileIdx];
      const byName = files[fileIdx]?.original_name;
      if (byName) {
        return preview.flights.find((f) => f.name === byName) ?? null;
      }
      return null;
    },
    [preview, files],
  );

  const fileTimeRange = useCallback(
    (fileIdx: number): [number, number] => {
      const flight = getPreviewFlight(fileIdx);
      return flight?.time_range ?? [0, 10];
    },
    [getPreviewFlight],
  );

  const getPhaseRange = useCallback(
    (phase: PhaseKey, fileIdx: number): FileRange => {
      const saved = phaseRanges[phase][fileIdx];
      if (saved) return saved;
      return fullRangeForFlight(getPreviewFlight(fileIdx));
    },
    [phaseRanges, getPreviewFlight],
  );

  useEffect(() => {
    if (files.length === 0) return;
    const fi = Math.min(selectedFileIdx, files.length - 1);
    setGeometryFileIdx((prev) => (prev < files.length ? prev : fi));
  }, [files.length, selectedFileIdx]);

  const checkCapabilities = useCallback(async () => {
    if (!sessionId || files.length === 0) return;
    try {
      const cap = await api.sysIdCapabilities({
        session_id: sessionId,
        file_idx: geometryFileIdx,
      });
      setCapWarnings(cap.ready ? [] : cap.missing);
    } catch {
      setCapWarnings(['Could not probe log capabilities']);
    }
  }, [sessionId, files.length, geometryFileIdx]);

  const loadDefaults = async () => {
    if (!sessionId || files.length === 0) return;
    try {
      const d = await api.sysIdDefaults({ session_id: sessionId, file_idx: geometryFileIdx });
      setModel((m) => ({
        ...m,
        mass: d.mass ?? m.mass,
        rotor_positions: d.rotor_positions ?? m.rotor_positions,
        rotor_thrust_directions: d.rotor_thrust_directions ?? m.rotor_thrust_directions,
        rotor_torque_directions: d.rotor_torque_directions ?? m.rotor_torque_directions,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load defaults');
    }
  };

  const loadPreview = async () => {
    if (!sessionId || files.length === 0) return;
    setError(null);
    try {
      const allIndices = files.map((_, i) => i);
      const data = await api.sysIdPreview({
        session_id: sessionId,
        file_indices: allIndices,
        model,
      });
      setPreview(data);
      setPhaseRanges((prev) => initPhaseRangesFromPreview(prev, data.flights));
      setPhaseEnabled((prev) => initPhaseEnabledFromPreview(prev, data.flights.length));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Preview failed');
    }
  };

  useEffect(() => {
    void checkCapabilities();
  }, [checkCapabilities]);

  useEffect(() => {
    if (sessionId && files.length > 0) {
      void loadPreview();
    }
  }, [sessionId, files.length, model.mass, model.rotor_positions, model.rotor_thrust_directions]);

  const buildTimeframesForPhase = useCallback(
    (phase: PhaseKey): { file_idx: number; start: number; end: number }[] =>
      files
        .map((_, i) => i)
        .filter((i) => isFileEnabledForPhase(phaseEnabled, phase, i))
        .map((file_idx) => ({ file_idx, ...getPhaseRange(phase, file_idx) })),
    [files, phaseEnabled, getPhaseRange],
  );

  const fileIndicesForRun = useMemo(() => {
    const indices = new Set<number>();
    for (const phase of PHASE_KEYS) {
      for (let i = 0; i < files.length; i++) {
        if (isFileEnabledForPhase(phaseEnabled, phase, i)) {
          indices.add(i);
        }
      }
    }
    return [...indices].sort((a, b) => a - b);
  }, [files.length, phaseEnabled]);

  const run = async () => {
    if (!sessionId) return;
    const timeframesThrust = buildTimeframesForPhase('thrust');
    const timeframesRp = buildTimeframesForPhase('inertia_rp');
    const timeframesYaw = buildTimeframesForPhase('inertia_yaw');
    if (!timeframesThrust.length || !timeframesRp.length || !timeframesYaw.length) {
      setError('Each analysis panel needs at least one file enabled for estimation.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.sysIdRun({
        session_id: sessionId,
        file_indices: fileIndicesForRun,
        model,
        exponents: [0, 1, 2],
        timeframes_thrust: timeframesThrust,
        timeframes_inertia_rp: timeframesRp,
        timeframes_inertia_yaw: timeframesYaw,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Estimation failed');
    } finally {
      setLoading(false);
    }
  };

  const updatePhaseRange = (phase: PhaseKey, fileIdx: number, start: number, end: number) => {
    setPhaseRanges((prev) => ({
      ...prev,
      [phase]: { ...prev[phase], [fileIdx]: { start, end } },
    }));
  };

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)] min-h-0">
      <div className="flex-1 flex flex-col gap-3 overflow-y-auto min-w-0">
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded px-3 py-2">
            {error}
          </div>
        )}
        {capWarnings.length > 0 && (
          <div className="text-sm text-amber-300 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
            Missing for sysid: {capWarnings.join(', ')}
          </div>
        )}

        {PHASE_KEYS.map((phase) => {
          const fileIdx = phaseFileIdx[phase];
          const fileActive = isFileEnabledForPhase(phaseEnabled, phase, fileIdx);
          const { start, end } = getPhaseRange(phase, fileIdx);
          const fileName = files[fileIdx]?.original_name ?? `File ${fileIdx}`;
          const flight = getPreviewFlight(fileIdx);
          const [rangeMin, rangeMax] = fileTimeRange(fileIdx);
          const phaseTraces = buildPhaseTraces(flight, phase, start, end);

          return (
            <div key={phase} className="border rounded p-3" style={{ borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-medium mb-2">{PHASE_LABELS[phase]}</h3>
              <div className="flex flex-wrap gap-3 items-center mb-2 text-xs">
                <label className="flex items-center gap-1">
                  File
                  <select
                    className="bg-black/30 border border-white/10 rounded px-1 py-0.5 max-w-[12rem]"
                    value={fileIdx}
                    onChange={(e) => {
                      const nextFileIdx = parseInt(e.target.value, 10);
                      setPhaseFileIdx((prev) => ({ ...prev, [phase]: nextFileIdx }));
                      setPhaseRanges((prev) => {
                        if (nextFileIdx in prev[phase]) return prev;
                        const flightForFile = preview?.flights[nextFileIdx];
                        return {
                          ...prev,
                          [phase]: {
                            ...prev[phase],
                            [nextFileIdx]: fullRangeForFlight(flightForFile),
                          },
                        };
                      });
                    }}
                  >
                    {files.map((f, i) => (
                      <option key={f.file_id} value={i}>
                        {f.original_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={fileActive}
                    onChange={(e) => {
                      setPhaseEnabled((prev) => ({
                        ...prev,
                        [phase]: { ...prev[phase], [fileIdx]: e.target.checked },
                      }));
                    }}
                  />
                  Enabled
                </label>
                <span className="text-[var(--text-secondary)]">
                  {start.toFixed(1)} – {end.toFixed(1)} s
                </span>
              </div>
              <EpochRangeSlider
                min={rangeMin}
                max={rangeMax}
                start={start}
                end={end}
                disabled={!fileActive}
                onCommit={(s, e) => updatePhaseRange(phase, fileIdx, s, e)}
              />
              <div
                className={`mt-3 min-h-[200px] ${!fileActive ? 'opacity-40 pointer-events-none' : ''}`}
                aria-disabled={!fileActive}
              >
                <p className="text-xs text-[var(--text-secondary)] mb-1">
                  {fileName} · {start.toFixed(1)}–{end.toFixed(1)} s
                  {!fileActive ? ' · excluded from estimation' : ''}
                </p>
                <Plot
                  data={fileActive ? phaseTraces : []}
                  layout={{
                    ...plotLayoutBase,
                    height: 200,
                    margin: { l: 50, r: 20, t: 28, b: 40 },
                    showlegend: true,
                    legend: { orientation: 'h', y: 1.12 },
                    uirevision: `${phase}-${fileIdx}`,
                    xaxis: { ...plotLayoutBase.xaxis, title: { text: 'Time [s]' } },
                    yaxis: { ...plotLayoutBase.yaxis, title: { text: 'Excitation' } },
                  }}
                  config={PREVIEW_PLOT_CONFIG}
                  className="w-full"
                />
              </div>
            </div>
          );
        })}

        {result && (
          <div className="border rounded p-3 space-y-3" style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-medium">Diagnostic plots</h3>
            <SysIdResultPlots result={result} />
          </div>
        )}
      </div>

      <aside
        className="w-96 shrink-0 border rounded p-3 overflow-y-auto overflow-x-hidden space-y-3 text-sm min-w-0"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}
      >
        <h2 className="font-medium">System ID</h2>
        <p className="text-xs text-[var(--text-secondary)]">
          Uses parsed log columns (accel, gyro, motor commands). Works with any firmware the log viewer
          supports.
        </p>

        <label className="block text-xs">
          Geometry source log
          <select
            className="w-full mt-0.5 px-2 py-1 rounded bg-black/30 border border-white/10 text-sm"
            value={geometryFileIdx}
            onChange={(e) => setGeometryFileIdx(parseInt(e.target.value, 10))}
          >
            {files.map((f, i) => (
              <option key={f.file_id} value={i}>
                {f.original_name}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="w-full py-1 rounded bg-white/10 hover:bg-white/15 text-xs"
          onClick={() => void loadDefaults()}
          disabled={files.length === 0}
        >
          Load geometry from log
        </button>

        <label className="block text-xs">
          Mass [kg]
          <input
            type="number"
            step="0.001"
            className="w-full mt-0.5 px-2 py-1 rounded bg-black/30 border border-white/10"
            value={model.mass}
            onChange={(e) => setModel((m) => ({ ...m, mass: parseFloat(e.target.value) || 0 }))}
          />
        </label>
        <label className="block text-xs">
          Inertia ratio (Izz extrapolation)
          <input
            type="number"
            step="0.01"
            className="w-full mt-0.5 px-2 py-1 rounded bg-black/30 border border-white/10"
            value={model.inertia_ratio ?? 1.832}
            onChange={(e) =>
              setModel((m) => ({ ...m, inertia_ratio: parseFloat(e.target.value) || 1.832 }))
            }
          />
        </label>

        <div className="space-y-2">
          <div className="text-xs text-[var(--text-secondary)]">Rotor geometry (FLU frame)</div>
          {[0, 1, 2, 3].map((ri) => (
            <div key={ri} className="space-y-0.5 border-t border-white/5 pt-1">
              <div className="text-[10px] text-[var(--text-secondary)]">Rotor {ri + 1}</div>
              <Vec3Input
                label="pos"
                value={model.rotor_positions[ri]}
                onChange={(v) => {
                  const next = model.rotor_positions.map((r, i) => (i === ri ? v : r));
                  setModel((m) => ({ ...m, rotor_positions: next }));
                }}
              />
              <Vec3Input
                label="thrust"
                value={model.rotor_thrust_directions[ri]}
                onChange={(v) => {
                  const next = model.rotor_thrust_directions.map((r, i) => (i === ri ? v : r));
                  setModel((m) => ({ ...m, rotor_thrust_directions: next }));
                }}
              />
              <Vec3Input
                label="torque"
                value={model.rotor_torque_directions[ri]}
                onChange={(v) => {
                  const next = model.rotor_torque_directions.map((r, i) => (i === ri ? v : r));
                  setModel((m) => ({ ...m, rotor_torque_directions: next }));
                }}
              />
            </div>
          ))}
        </div>

        <button
          type="button"
          className="w-full py-2 rounded bg-blue-700 hover:bg-blue-600 font-medium disabled:opacity-50"
          disabled={
            loading ||
            !sessionId ||
            files.length === 0 ||
            fileIndicesForRun.length === 0 ||
            PHASE_KEYS.some((phase) => buildTimeframesForPhase(phase).length === 0)
          }
          onClick={() => void run()}
        >
          {loading ? 'Running…' : 'Run estimation'}
        </button>

        {result && <EstimationSummary result={result} />}
      </aside>
    </div>
  );
}

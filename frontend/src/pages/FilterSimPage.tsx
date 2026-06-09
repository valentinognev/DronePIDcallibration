import { useState } from 'react';
import Plot from '../components/Plot';
import { adaptPlotLineColor, INTERACTIVE_PLOT_CONFIG } from '../lib/constants';
import { api } from '../lib/api';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';

type FilterResponse = Record<string, number[]>;

const PLOT_ROWS = [
  { key: 'magnitude_db', yLabel: 'Magnitude (dB)', xLabel: 'Frequency (Hz)' },
  { key: 'group_delay_ms', yLabel: 'Filter Delay (ms)', xLabel: 'Frequency (Hz)' },
  { key: 'phase_deg', yLabel: 'Phase Delay (deg)', xLabel: 'Frequency (Hz)' },
  { key: 'step_response', yLabel: 'Step Resp.', xLabel: 'Time (ms)' },
] as const;

const PLOT_HEIGHT = 180;
const ROW_GRID_COLS = '1.25rem 1fr';

function sumDelayMs(responses: FilterResponse[]): number {
  return responses.reduce((sum, r) => sum + Number(r.total_delay_ms ?? 0), 0);
}

function FilterPlotCell({
  responses,
  rowKey,
  colors,
  namePrefix,
  plotLayoutBase,
}: {
  responses: FilterResponse[];
  rowKey: (typeof PLOT_ROWS)[number]['key'];
  colors: string[];
  namePrefix: string;
  plotLayoutBase: ReturnType<typeof usePlotLayoutBase>;
}) {
  const isStep = rowKey === 'step_response';

  return (
    <Plot
      data={responses.map((r, i) => ({
        x: isStep ? r.step_time_ms : r.freq_hz,
        y: r[rowKey],
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: `${namePrefix} ${i + 1}`,
        line: { color: colors[i % colors.length] },
      }))}
      layout={{
        ...plotLayoutBase,
        height: PLOT_HEIGHT,
        margin: { ...plotLayoutBase.margin, t: 8, l: 42, r: 10, b: 32 },
        showlegend: false,
        xaxis: { ...plotLayoutBase.xaxis, title: '' },
        yaxis: { ...plotLayoutBase.yaxis, title: '' },
      }}
      config={INTERACTIVE_PLOT_CONFIG}
      style={{ width: '100%', height: PLOT_HEIGHT }}
      useResizeHandler
    />
  );
}

function FilterColumn({
  title,
  delayMs,
  responses,
  colors,
  namePrefix,
  plotLayoutBase,
}: {
  title: string;
  delayMs: number;
  responses: FilterResponse[];
  colors: string[];
  namePrefix: string;
  plotLayoutBase: ReturnType<typeof usePlotLayoutBase>;
}) {
  if (responses.length === 0) return null;

  return (
    <div className="flex flex-col gap-1 min-w-0">
      <h3 className="text-sm font-semibold text-center text-[var(--text-primary)] shrink-0">
        {title} | Delay {delayMs.toFixed(5)} ms
      </h3>
      {PLOT_ROWS.map((row) => (
        <div
          key={row.key}
          className="grid gap-x-1 min-w-0"
          style={{ gridTemplateColumns: ROW_GRID_COLS }}
        >
          <div
            className="flex items-center justify-center text-xs text-[var(--text-secondary)]"
            aria-hidden
          >
            <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap text-center">
              {row.yLabel}
            </span>
          </div>
          <div className="min-w-0">
            <FilterPlotCell
              responses={responses}
              rowKey={row.key}
              colors={colors}
              namePrefix={namePrefix}
              plotLayoutBase={plotLayoutBase}
            />
          </div>
          <div aria-hidden />
          <p className="text-xs text-center text-[var(--text-secondary)]">{row.xLabel}</p>
        </div>
      ))}
    </div>
  );
}

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

  const lpf = (data?.lpf as FilterResponse[]) || [];
  const notch = (data?.notch as FilterResponse[]) || [];
  const combined = data?.combined as FilterResponse | undefined;
  const totalDelayMs = Number(data?.total_delay_ms ?? 0);

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 flex flex-col gap-3 overflow-auto min-h-0 min-w-0">
        {data === null ? (
          <div className="panel flex items-center justify-center text-sm text-[var(--text-secondary)] h-[600px]">
            Run analysis to display filter responses
          </div>
        ) : (
          <>
            <div
              className="grid gap-3 min-w-0"
              style={{ gridTemplateColumns: '1fr 1fr' }}
            >
              <FilterColumn
                title="LOWPASS FILTERS"
                delayMs={sumDelayMs(lpf)}
                responses={lpf}
                colors={['#00cccc', '#00ff00']}
                namePrefix="LPF"
                plotLayoutBase={plotLayoutBase}
              />
              <FilterColumn
                title="NOTCH FILTERS"
                delayMs={sumDelayMs(notch)}
                responses={notch}
                colors={['#ff0000', '#ff9900', '#ffff00']}
                namePrefix="Notch"
                plotLayoutBase={plotLayoutBase}
              />
            </div>
            {combined && (
              <div className="flex flex-col gap-1 min-w-0">
                <h3 className="text-sm font-semibold text-center text-[var(--text-primary)] shrink-0">
                  Combined | Total Delay: {totalDelayMs.toFixed(3)} ms
                </h3>
                <div className="grid gap-x-1 min-w-0" style={{ gridTemplateColumns: ROW_GRID_COLS }}>
                  <div
                    className="flex items-center justify-center text-xs text-[var(--text-secondary)]"
                    aria-hidden
                  >
                    <span className="[writing-mode:vertical-rl] rotate-180 whitespace-nowrap">
                      Magnitude (dB)
                    </span>
                  </div>
                  <div className="min-w-0">
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
                        height: 200,
                        margin: { ...plotLayoutBase.margin, t: 8, l: 42, r: 10, b: 36 },
                        xaxis: { ...plotLayoutBase.xaxis, title: '' },
                        yaxis: { ...plotLayoutBase.yaxis, title: '' },
                      }}
                      config={INTERACTIVE_PLOT_CONFIG}
                      style={{ width: '100%', height: 200 }}
                      useResizeHandler
                    />
                  </div>
                  <div aria-hidden />
                  <p className="text-xs text-center text-[var(--text-secondary)]">Frequency (Hz)</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">Filter Controls</h3>
        <label className="text-xs">Looprate (Hz)</label>
        <input
          className="select-input"
          type="number"
          value={looprate}
          onChange={(e) => setLooprate(Number(e.target.value))}
        />
        <label className="text-xs">LPF pt1 #1 (Hz)</label>
        <input
          className="select-input"
          type="number"
          value={lpf1}
          onChange={(e) => setLpf1(Number(e.target.value))}
        />
        <label className="text-xs">LPF pt1 #2 (Hz)</label>
        <input
          className="select-input"
          type="number"
          value={lpf2}
          onChange={(e) => setLpf2(Number(e.target.value))}
        />
        <label className="text-xs">Notch freq (Hz)</label>
        <input
          className="select-input"
          type="number"
          value={notchFreq}
          onChange={(e) => setNotchFreq(Number(e.target.value))}
        />
        <label className="text-xs">Notch Q</label>
        <input
          className="select-input"
          type="number"
          value={notchQ}
          onChange={(e) => setNotchQ(Number(e.target.value))}
        />
        <button className="btn-run w-full" onClick={run} disabled={loading}>
          {loading ? 'Running...' : 'Run'}
        </button>
        {data && (
          <p className="text-red-400 text-sm font-semibold">
            Filter Delay Total: {totalDelayMs.toFixed(4)} ms
          </p>
        )}
      </div>
    </div>
  );
}

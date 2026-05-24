import { useState } from 'react';
import Plot from '../components/Plot';
import { AxisSelector } from '../components/AxisSelector';
import { api } from '../lib/api';
import { usePlotLayoutBase } from '../hooks/useAppTheme';
import { useSessionStore } from '../store/sessionStore';

export function StatsPage() {
  const plotLayoutBase = usePlotLayoutBase();
  const { sessionId, selectedFileIdx } = useSessionStore();
  const [axis, setAxis] = useState(0);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [motorNoise, setMotorNoise] = useState<Record<string, { freq: number[]; psd: number[] }>>({});
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.runStats({
        session_id: sessionId,
        file_idx: selectedFileIdx,
        axis,
      });
      setStats(result.stats as Record<string, unknown>);
      setMotorNoise(result.motor_noise as typeof motorNoise);
    } finally {
      setLoading(false);
    }
  };

  const balance = stats?.term_balance as Record<string, number> | undefined;

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <div className="flex-1 grid grid-cols-2 gap-4">
        <div className="panel">
          <h3 className="font-semibold mb-3">PID Statistics</h3>
          {stats ? (
            <dl className="space-y-2 text-sm">
              <StatRow label="PID Error RMS" value={Number(stats.pid_error_rms).toFixed(2)} />
              <StatRow label="PID Sum RMS" value={Number(stats.pid_sum_rms).toFixed(2)} />
              <StatRow label="Gyro RMS" value={Number(stats.gyro_rms).toFixed(2)} />
              <StatRow label="Motor Band Power" value={Number(stats.motor_band_power).toFixed(4)} />
              <StatRow label="Low Band Power" value={Number(stats.low_band_power).toFixed(4)} />
              <StatRow label="Tracking Error Mean" value={Number(stats.tracking_error_mean).toFixed(2)} />
            </dl>
          ) : (
            <p className="text-[var(--text-secondary)]">Run analysis to see stats</p>
          )}
        </div>

        <div className="panel">
          <h3 className="font-semibold mb-3">Term Balance</h3>
          {balance && (
            <Plot
              data={[
                {
                  labels: ['P', 'I', 'D', 'F'],
                  values: [balance.P_pct, balance.I_pct, balance.D_pct, balance.F_pct],
                  type: 'pie',
                  marker: { colors: ['#00b300', '#1a66cc', '#ff9900', '#ff33cc'] },
                },
              ]}
              layout={{ ...plotLayoutBase, height: 300, showlegend: true }}
              config={{ responsive: true }}
              style={{ width: '100%' }}
            />
          )}
        </div>

        <div className="panel col-span-2">
          <h3 className="font-semibold mb-3">Motor Noise</h3>
          <Plot
            data={Object.entries(motorNoise).map(([name, d], i) => ({
              x: d.freq,
              y: d.psd,
              type: 'scatter',
              mode: 'lines',
              name,
              line: { color: ['#e60000', '#ff9900', '#0099ff', '#00cccc'][i] },
            }))}
            layout={{
              ...plotLayoutBase,
              height: 300,
              xaxis: { ...plotLayoutBase.xaxis, title: 'Frequency (Hz)' },
              yaxis: { ...plotLayoutBase.yaxis, title: 'PSD (dB)' },
            }}
            config={{ responsive: true }}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      <div className="panel w-56 space-y-3 shrink-0">
        <h3 className="font-semibold text-sm">PID Stats</h3>
        <AxisSelector selected={axis} onChange={setAxis} />
        <button className="btn-run w-full" onClick={run} disabled={loading || !sessionId}>
          Run
        </button>
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-[var(--text-secondary)]">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}

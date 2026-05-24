import { getTraceColor } from '../lib/constants';
import { useAppTheme } from '../hooks/useAppTheme';

interface Props {
  traces: string[];
  visible: string[];
  onToggle: (trace: string) => void;
  yScale: number;
  onYScaleChange: (v: number) => void;
}

const TRACE_LABELS: Record<string, string> = {
  gyro: 'Gyro',
  gyro_pf: 'Gyro(pf)',
  pterm: 'P-term',
  iterm: 'I-term',
  dterm_pf: 'D-term(pf)',
  dterm: 'D-term',
  fterm: 'F-term',
  setpoint: 'Set point',
  pidsum: 'PID sum',
  piderr: 'PID error',
  throttle: 'Throttle',
  motor_0: 'Motor 1',
  motor_1: 'Motor 2',
  motor_2: 'Motor 3',
  motor_3: 'Motor 4',
  debug: 'Debug',
};

export function TraceTogglePanel({ traces, visible, onToggle, yScale, onYScaleChange }: Props) {
  const theme = useAppTheme();

  return (
    <div className="panel w-48 shrink-0 overflow-y-auto max-h-full">
      <h3 className="text-sm font-semibold mb-2">Selection</h3>
      <label className="text-xs text-[var(--text-secondary)] block mb-1">y scale</label>
      <input
        type="number"
        className="select-input mb-3 w-20"
        value={yScale}
        onChange={(e) => onYScaleChange(Number(e.target.value))}
      />
      <div className="space-y-1">
        {traces.map((t) => (
          <label key={t} className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={visible.includes(t)}
              onChange={() => onToggle(t)}
            />
            <span style={{ color: getTraceColor(t, theme) }}>{TRACE_LABELS[t] || t}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

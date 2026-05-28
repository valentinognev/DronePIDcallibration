import { getTraceColor, TRACE_LABELS } from '../lib/constants';
import { useAppTheme } from '../hooks/useAppTheme';

interface Props {
  traces: string[];
  visible: string[];
  onToggle: (trace: string) => void;
  yScale: number;
  onYScaleChange: (v: number) => void;
}

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

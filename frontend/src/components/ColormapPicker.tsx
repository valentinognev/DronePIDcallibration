import { COLORMAPS } from '../lib/constants';

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export function ColormapPicker({ value, onChange }: Props) {
  return (
    <select className="select-input" value={value} onChange={(e) => onChange(e.target.value)}>
      {COLORMAPS.map((c) => (
        <option key={c} value={c}>{c}</option>
      ))}
    </select>
  );
}

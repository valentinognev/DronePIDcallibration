interface Props {
  selected: number;
  onChange: (axis: number) => void;
  labels?: string[];
}

export function AxisSelector({ selected, onChange, labels = ['R', 'P', 'Y'] }: Props) {
  return (
    <div className="flex gap-2">
      {labels.map((l, i) => (
        <label key={l} className="flex items-center gap-1 text-sm cursor-pointer">
          <input
            type="radio"
            name="axis"
            checked={selected === i}
            onChange={() => onChange(i)}
          />
          {l}
        </label>
      ))}
    </div>
  );
}

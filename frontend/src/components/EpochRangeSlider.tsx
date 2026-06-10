import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface Props {
  min: number;
  max: number;
  start: number;
  end: number;
  onCommit: (start: number, end: number) => void;
  disabled?: boolean;
}

const MIN_GAP = 0.1;
const STEP = 0.1;

function roundTime(value: number): number {
  return Math.round(value * 10) / 10;
}

function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value));
}

function formatTime(seconds: number): string {
  return `${seconds.toFixed(1)} s`;
}

function computeTimeTicks(min: number, max: number, maxTicks = 8): number[] {
  const span = max - min;
  if (span <= 0) return [min];

  const rawStep = span / maxTicks;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  let niceStep: number;
  if (normalized <= 1) niceStep = magnitude;
  else if (normalized <= 2) niceStep = 2 * magnitude;
  else if (normalized <= 5) niceStep = 5 * magnitude;
  else niceStep = 10 * magnitude;

  const ticks: number[] = [];
  const start = Math.ceil(min / niceStep) * niceStep;
  for (let t = start; t <= max + niceStep * 0.001; t += niceStep) {
    ticks.push(roundTime(t));
  }
  if (ticks.length === 0 || ticks[0] > min + 0.05) {
    ticks.unshift(roundTime(min));
  }
  const last = ticks[ticks.length - 1];
  if (last < max - 0.05) {
    ticks.push(roundTime(max));
  }
  return ticks;
}

export function EpochRangeSlider({ min, max, start, end, onCommit, disabled }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef<'start' | 'end' | null>(null);
  const dragValues = useRef({ start, end });
  const [localStart, setLocalStart] = useState(start);
  const [localEnd, setLocalEnd] = useState(end);

  useEffect(() => {
    if (!dragging.current) {
      dragValues.current = { start, end };
      setLocalStart(start);
      setLocalEnd(end);
    }
  }, [start, end]);

  const span = max - min;
  const toPct = useCallback(
    (value: number) => (span <= 0 ? 0 : ((value - min) / span) * 100),
    [min, span],
  );

  const valueFromClientX = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track || span <= 0) return min;
      const rect = track.getBoundingClientRect();
      const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
      return roundTime(min + ratio * span);
    },
    [min, span],
  );

  const commitRange = useCallback(
    (nextStart: number, nextEnd: number) => {
      const s = roundTime(clamp(nextStart, min, max - MIN_GAP));
      const e = roundTime(clamp(nextEnd, min + MIN_GAP, max));
      const [lo, hi] = s <= e ? [s, e] : [e, s];
      const finalStart = hi - lo < MIN_GAP ? roundTime(hi - MIN_GAP) : lo;
      dragValues.current = { start: finalStart, end: hi };
      setLocalStart(finalStart);
      setLocalEnd(hi);
      onCommit(finalStart, hi);
    },
    [max, min, onCommit],
  );

  const handlePointerDown = (handle: 'start' | 'end') => (e: React.PointerEvent) => {
    if (disabled) return;
    e.preventDefault();
    dragging.current = handle;
    dragValues.current = { start: localStart, end: localEnd };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const handle = dragging.current;
    if (!handle || disabled) return;

    const value = valueFromClientX(e.clientX);
    if (handle === 'start') {
      const next = roundTime(clamp(value, min, dragValues.current.end - MIN_GAP));
      dragValues.current.start = next;
      setLocalStart(next);
    } else {
      const next = roundTime(clamp(value, dragValues.current.start + MIN_GAP, max));
      dragValues.current.end = next;
      setLocalEnd(next);
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!dragging.current || disabled) return;
    dragging.current = null;
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    commitRange(dragValues.current.start, dragValues.current.end);
  };

  const startPct = toPct(localStart);
  const endPct = toPct(localEnd);
  const axisTicks = useMemo(() => computeTimeTicks(min, max), [min, max]);

  return (
    <div className={`panel py-2 px-3 ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
      <div className="flex items-center justify-between mb-2 text-xs text-[var(--text-secondary)]">
        <span className="font-medium text-[var(--text-primary)]">Analysis window</span>
        <span>
          {formatTime(localStart)} – {formatTime(localEnd)}
          <span className="ml-2 opacity-70">({formatTime(localEnd - localStart)} selected)</span>
        </span>
      </div>

      <div
        ref={trackRef}
        className="relative h-8 select-none touch-none"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div
          className="absolute top-1/2 -translate-y-1/2 h-2 w-full rounded-full"
          style={{ background: 'var(--bg-secondary)' }}
        />

        <div
          className="absolute top-1/2 -translate-y-1/2 h-2 rounded-full"
          style={{
            left: `${startPct}%`,
            width: `${endPct - startPct}%`,
            background: 'var(--accent-blue)',
            opacity: 0.55,
          }}
        />

        {startPct > 0 && (
          <div
            className="absolute top-1/2 -translate-y-1/2 h-2 rounded-l-full"
            style={{
              left: 0,
              width: `${startPct}%`,
              background: 'var(--bg-primary)',
              opacity: 0.65,
            }}
          />
        )}

        {endPct < 100 && (
          <div
            className="absolute top-1/2 -translate-y-1/2 h-2 rounded-r-full"
            style={{
              left: `${endPct}%`,
              width: `${100 - endPct}%`,
              background: 'var(--bg-primary)',
              opacity: 0.65,
            }}
          />
        )}

        {(['start', 'end'] as const).map((handle) => {
          const pct = handle === 'start' ? startPct : endPct;
          const value = handle === 'start' ? localStart : localEnd;
          return (
            <button
              key={handle}
              type="button"
              aria-label={handle === 'start' ? 'Start time' : 'End time'}
              aria-valuemin={min}
              aria-valuemax={max}
              aria-valuenow={value}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full border-2 cursor-grab active:cursor-grabbing focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
              style={{
                left: `${pct}%`,
                background: 'var(--text-primary)',
                borderColor: 'var(--accent-blue)',
              }}
              onPointerDown={handlePointerDown(handle)}
            />
          );
        })}
      </div>

      <div className="relative mt-1 h-5">
        {axisTicks.map((tick) => {
          const pct = toPct(tick);
          const isHandle =
            Math.abs(tick - localStart) < 0.05 || Math.abs(tick - localEnd) < 0.05;
          if (isHandle) return null;
          return (
            <span
              key={tick}
              className="absolute top-0 -translate-x-1/2 text-[10px] text-[var(--text-secondary)] whitespace-nowrap"
              style={{ left: `${pct}%` }}
            >
              <span
                className="absolute bottom-full left-1/2 -translate-x-1/2 mb-0.5 w-px h-1.5"
                style={{ background: 'var(--text-secondary)', opacity: 0.45 }}
              />
              {formatTime(tick)}
            </span>
          );
        })}
        {(['start', 'end'] as const).map((handle) => {
          const value = handle === 'start' ? localStart : localEnd;
          const pct = handle === 'start' ? startPct : endPct;
          return (
            <span
              key={handle}
              className="absolute top-0 -translate-x-1/2 text-[10px] font-medium whitespace-nowrap"
              style={{ left: `${pct}%`, color: 'var(--accent-blue)' }}
            >
              <span
                className="absolute bottom-full left-1/2 -translate-x-1/2 mb-0.5 w-0.5 h-2 rounded-sm"
                style={{ background: 'var(--accent-blue)' }}
              />
              {formatTime(value)}
            </span>
          );
        })}
      </div>

      <div className="sr-only">
        <input
          type="range"
          min={min}
          max={max}
          step={STEP}
          value={localStart}
          onChange={(e) => commitRange(Number(e.target.value), localEnd)}
          tabIndex={-1}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={STEP}
          value={localEnd}
          onChange={(e) => commitRange(localStart, Number(e.target.value))}
          tabIndex={-1}
        />
      </div>
    </div>
  );
}

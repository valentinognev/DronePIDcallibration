import { useCallback, useMemo, useRef } from 'react';
import Plot from './Plot';
import { adaptPlotLineColor } from '../lib/constants';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';
import { savePlotlyFigure } from '../lib/utils';

interface Trace {
  key: string;
  label: string;
  color: string;
  x: number[];
  y: number[];
  yaxis?: 'y' | 'y2';
}

interface EpochTrim {
  start: number;
  end: number;
  onCommit: (start: number, end: number) => void;
}

interface Props {
  title: string;
  traces: Trace[];
  yLabel: string;
  yLabel2?: string;
  yRange?: [number, number];
  dualAxis?: boolean;
  lineWidth?: number;
  height?: number;
  showLegend?: boolean;
  epochTrim?: EpochTrim;
  saveFilename?: string;
}

const MIN_EPOCH_GAP = 0.1;

function roundTime(value: number): number {
  return Math.round(value * 10) / 10;
}

function epochShapes(start: number, end: number) {
  const line = { color: 'rgba(59, 130, 246, 0.9)', width: 2, dash: 'dot' as const };
  return [
    {
      type: 'line' as const,
      x0: start,
      x1: start,
      y0: 0,
      y1: 1,
      yref: 'paper' as const,
      line,
      editable: true,
    },
    {
      type: 'line' as const,
      x0: end,
      x1: end,
      y0: 0,
      y1: 1,
      yref: 'paper' as const,
      line,
      editable: true,
    },
  ];
}

export function TimeSeriesPlot({
  title,
  traces,
  yLabel,
  yLabel2,
  yRange,
  dualAxis = false,
  lineWidth = 2,
  height = 200,
  showLegend = false,
  epochTrim,
  saveFilename,
}: Props) {
  const theme = useAppTheme();
  const plotLayoutBase = usePlotLayoutBase();
  const containerRef = useRef<HTMLDivElement>(null);

  const xRange = useMemo(() => {
    if (!epochTrim || traces.length === 0) return undefined;
    const xs = traces.flatMap((t) => t.x);
    if (xs.length === 0) return undefined;
    return [Math.min(...xs), Math.max(...xs)] as [number, number];
  }, [epochTrim, traces]);

  const handleRelayout = useCallback(
    (event: Plotly.PlotRelayoutEvent) => {
      if (!epochTrim || !xRange) return;

      let nextStart = epochTrim.start;
      let nextEnd = epochTrim.end;

      for (const [key, value] of Object.entries(event)) {
        if (typeof value !== 'number') continue;
        if (key === 'shapes[0].x0' || key === 'shapes[0].x1') nextStart = value;
        if (key === 'shapes[1].x0' || key === 'shapes[1].x1') nextEnd = value;
      }

      const [fullMin, fullMax] = xRange;
      nextStart = roundTime(Math.max(fullMin, Math.min(nextStart, nextEnd - MIN_EPOCH_GAP)));
      nextEnd = roundTime(Math.min(fullMax, Math.max(nextEnd, nextStart + MIN_EPOCH_GAP)));

      if (nextStart !== epochTrim.start || nextEnd !== epochTrim.end) {
        epochTrim.onCommit(nextStart, nextEnd);
      }
    },
    [epochTrim, xRange],
  );

  const handleSave = useCallback(async () => {
    const plotEl = containerRef.current?.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (!plotEl || !saveFilename) return;
    await savePlotlyFigure(plotEl, saveFilename);
  }, [saveFilename]);

  return (
    <div ref={containerRef} className="shrink-0 w-full relative" style={{ minHeight: height }}>
      {saveFilename && (
        <button
          type="button"
          className="absolute top-1 right-1 z-10 btn-run text-[10px] px-2 py-0.5 opacity-70 hover:opacity-100"
          onClick={handleSave}
          title="Save figure as PNG"
        >
          Save
        </button>
      )}
      <Plot
        data={traces.map((t) => ({
          x: t.x,
          y: t.y,
          type: 'scatter',
          mode: 'lines',
          name: t.label,
          line: { color: adaptPlotLineColor(t.color, theme), width: lineWidth },
          ...(dualAxis && t.yaxis === 'y2' ? { yaxis: 'y2' as const } : {}),
        }))}
        layout={{
          ...plotLayoutBase,
          title: { text: title, font: { size: 12 } },
          height,
          showlegend: showLegend,
          xaxis: { ...plotLayoutBase.xaxis, title: 'Time (s)', range: xRange },
          yaxis: {
            ...plotLayoutBase.yaxis,
            title: yLabel,
            range: yRange,
          },
          ...(dualAxis
            ? {
                yaxis2: {
                  ...plotLayoutBase.yaxis,
                  title: yLabel2 ?? 'Motor (RPM)',
                  overlaying: 'y',
                  side: 'right',
                  showgrid: false,
                },
              }
            : {}),
          ...(epochTrim ? { shapes: epochShapes(epochTrim.start, epochTrim.end) as Partial<Plotly.Layout>['shapes'] } : {}),
        }}
        config={{
          displayModeBar: true,
          responsive: true,
          ...(epochTrim ? { editable: true, edits: { shapePosition: true } } : {}),
        }}
        onRelayout={epochTrim ? handleRelayout : undefined}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}

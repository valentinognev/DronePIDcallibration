import { useCallback, useRef } from 'react';
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
  saveFilename?: string;
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
  saveFilename,
}: Props) {
  const theme = useAppTheme();
  const plotLayoutBase = usePlotLayoutBase();
  const containerRef = useRef<HTMLDivElement>(null);

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
        key={traces.map((t) => t.key).join('|') || 'empty'}
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
          xaxis: { ...plotLayoutBase.xaxis, title: 'Time (s)' },
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
        }}
        config={{
          displayModeBar: true,
          responsive: true,
        }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}

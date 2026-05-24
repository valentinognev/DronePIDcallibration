import Plot from './Plot';
import { adaptPlotLineColor } from '../lib/constants';
import { useAppTheme, usePlotLayoutBase } from '../hooks/useAppTheme';

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
}: Props) {
  const theme = useAppTheme();
  const plotLayoutBase = usePlotLayoutBase();

  return (
    <div className="shrink-0 w-full" style={{ minHeight: height }}>
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
        config={{ displayModeBar: true, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}

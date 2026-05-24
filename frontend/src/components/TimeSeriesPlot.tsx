import Plot from 'react-plotly.js';
import { PLOT_LAYOUT_BASE } from '../lib/constants';

interface Trace {
  key: string;
  label: string;
  color: string;
  x: number[];
  y: number[];
}

interface Props {
  title: string;
  traces: Trace[];
  yLabel: string;
  yRange?: [number, number];
  lineWidth?: number;
  height?: number;
  showLegend?: boolean;
}

export function TimeSeriesPlot({
  title,
  traces,
  yLabel,
  yRange,
  lineWidth = 2,
  height = 200,
  showLegend = false,
}: Props) {
  return (
    <Plot
      data={traces.map((t) => ({
        x: t.x,
        y: t.y,
        type: 'scatter',
        mode: 'lines',
        name: t.label,
        line: { color: t.color, width: lineWidth },
      }))}
      layout={{
        ...PLOT_LAYOUT_BASE,
        title: { text: title, font: { size: 12 } },
        height,
        showlegend: showLegend,
        xaxis: { ...PLOT_LAYOUT_BASE.xaxis, title: 'Time (s)' },
        yaxis: {
          ...PLOT_LAYOUT_BASE.yaxis,
          title: yLabel,
          range: yRange,
        },
      }}
      config={{ displayModeBar: true, responsive: true }}
      style={{ width: '100%' }}
      useResizeHandler
    />
  );
}

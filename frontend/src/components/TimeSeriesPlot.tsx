import Plot from './Plot';
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
  // #region agent log
  fetch('http://127.0.0.1:7808/ingest/b08aba62-617c-4296-b2d6-97342ac54eb4',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'93a084'},body:JSON.stringify({sessionId:'93a084',location:'TimeSeriesPlot.tsx:render',message:'plot render',data:{title,traceCount:traces.length,traceKeys:traces.map(t=>t.key),pointCount:traces[0]?.x?.length??0},timestamp:Date.now(),hypothesisId:'H3,H4'})}).catch(()=>{});
  // #endregion
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

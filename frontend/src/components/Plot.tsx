import { forwardRef } from 'react';
import type { ComponentProps } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js/dist/plotly.js';
import { useAppTheme } from '../hooks/useAppTheme';

const createPlot =
  typeof createPlotlyComponent === 'function'
    ? createPlotlyComponent
    : (createPlotlyComponent as { default: typeof createPlotlyComponent }).default;

const plotly =
  typeof Plotly === 'object' && Plotly !== null && 'default' in Plotly
    ? (Plotly as { default: typeof Plotly }).default
    : Plotly;

const PlotlyPlot = createPlot(plotly);

type PlotProps = ComponentProps<typeof PlotlyPlot>;

const Plot = forwardRef<HTMLDivElement, PlotProps>(function Plot(props, ref) {
  const theme = useAppTheme();
  return <PlotlyPlot {...props} ref={ref} key={theme} />;
});

export default Plot;

export type { PlotProps };

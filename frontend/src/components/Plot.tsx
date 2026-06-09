import { forwardRef, useEffect, useRef } from 'react';
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
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    let raf = 0;
    const resizePlot = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const plotEl = wrapper.querySelector('.js-plotly-plot') as HTMLElement | null;
        if (!plotEl || plotEl.offsetParent === null) return;
        const lib = plotly as { Plots?: { resize: (el: HTMLElement) => void } };
        lib.Plots?.resize(plotEl);
      });
    };

    const observer = new ResizeObserver(resizePlot);
    observer.observe(wrapper);
    resizePlot();
    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [theme]);

  return (
    <div ref={wrapperRef} className="w-full min-w-0">
      <PlotlyPlot {...props} ref={ref} key={theme} />
    </div>
  );
});

export default Plot;

export type { PlotProps };

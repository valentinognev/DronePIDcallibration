declare module 'react-plotly.js' {
  import { Component } from 'react';
  import { PlotParams } from 'plotly.js';

  export default class Plot extends Component<PlotParams> {}
}

declare module 'react-plotly.js/factory' {
  import { ComponentType } from 'react';

  export default function createPlotlyComponent(
    plotly: object,
  ): ComponentType<Record<string, unknown>>;
}

declare module 'plotly.js/dist/plotly.js' {
  const Plotly: object;
  export default Plotly;
}

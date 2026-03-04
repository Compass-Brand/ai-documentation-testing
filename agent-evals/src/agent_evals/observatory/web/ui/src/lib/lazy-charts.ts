import { lazy } from "react";

/**
 * Lazy-loaded chart components that defer chart.js registration
 * until the component is actually rendered. This avoids importing
 * chart.js (~60kb) eagerly in every page that uses charts.
 */

export const LazyBar = lazy(() =>
  import("chart.js").then((chartjs) => {
    chartjs.Chart.register(
      chartjs.CategoryScale,
      chartjs.LinearScale,
      chartjs.BarElement,
      chartjs.Tooltip,
      chartjs.Legend,
    );
    return import("react-chartjs-2").then((m) => ({ default: m.Bar }));
  }),
);

export const LazyLine = lazy(() =>
  import("chart.js").then((chartjs) => {
    chartjs.Chart.register(
      chartjs.CategoryScale,
      chartjs.LinearScale,
      chartjs.PointElement,
      chartjs.LineElement,
      chartjs.Filler,
      chartjs.Tooltip,
    );
    return import("react-chartjs-2").then((m) => ({ default: m.Line }));
  }),
);

export const LazyDoughnut = lazy(() =>
  import("chart.js").then((chartjs) => {
    chartjs.Chart.register(
      chartjs.ArcElement,
      chartjs.Tooltip,
      chartjs.Legend,
    );
    return import("react-chartjs-2").then((m) => ({ default: m.Doughnut }));
  }),
);

export const LazyRadar = lazy(() =>
  import("chart.js").then((chartjs) => {
    chartjs.Chart.register(
      chartjs.RadialLinearScale,
      chartjs.PointElement,
      chartjs.LineElement,
      chartjs.Filler,
      chartjs.Tooltip,
      chartjs.Legend,
    );
    return import("react-chartjs-2").then((m) => ({ default: m.Radar }));
  }),
);

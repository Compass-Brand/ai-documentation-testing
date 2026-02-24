import { defaults } from "chart.js";

export function applyBrandTheme() {
  defaults.font.family = "Inter, sans-serif";
  defaults.font.size = 12;
  defaults.color = "#5C6B7F"; // Slate Horizon

  defaults.plugins.legend.labels.usePointStyle = true;
  defaults.plugins.legend.labels.padding = 16;

  defaults.scale.grid.color = "rgba(229, 229, 229, 0.5)"; // Mist Grey 50%
  (defaults.scale as Record<string, unknown>)["border"] = { color: "#E5E5E5" };
  defaults.scale.ticks.padding = 8;
}

export const CHART_COLORS = {
  primary: "#C2A676",     // Goldenrod — primary trend line
  secondary: "#5C6B7F",   // Slate — secondary data
  success: "#4A5D4E",     // Sage
  warning: "#D4A84B",     // Amber
  error: "#A05040",       // Clay
  grid: "rgba(229, 229, 229, 0.5)",
} as const;

export const CHART_LINE_WIDTHS = {
  primary: 2,
  secondary: 1,
  grid: 1,
} as const;

export const CHART_BACKGROUNDS = {
  transparent: "transparent",
  subtle: "rgba(74, 93, 78, 0.05)", // 5% Sage Wisdom
} as const;

export const CHART_PROJECTION = {
  borderDash: [6, 4],
  borderColor: "#1A1A1A", // Deep Charcoal
  borderWidth: 1,
} as const;

export const CHART_ANIMATION = {
  duration: 600,
  easing: "easeOutQuart" as const,
} as const;

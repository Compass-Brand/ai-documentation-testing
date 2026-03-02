import { describe, it, expect } from "vitest";
import {
  CHART_COLORS,
  CHART_LINE_WIDTHS,
  CHART_BACKGROUNDS,
  CHART_PROJECTION,
  CHART_ANIMATION,
} from "../lib/chart-theme";

describe("chart-theme constants", () => {
  it("should export CHART_COLORS with all brand colors", () => {
    expect(CHART_COLORS.primary).toBe("#C2A676");
    expect(CHART_COLORS.secondary).toBe("#5C6B7F");
    expect(CHART_COLORS.success).toBe("#4A5D4E");
    expect(CHART_COLORS.warning).toBe("#D4A84B");
    expect(CHART_COLORS.error).toBe("#A05040");
    expect(CHART_COLORS.grid).toBe("rgba(229, 229, 229, 0.5)");
  });

  it("should export CHART_LINE_WIDTHS", () => {
    expect(CHART_LINE_WIDTHS.primary).toBe(2);
    expect(CHART_LINE_WIDTHS.secondary).toBe(1);
    expect(CHART_LINE_WIDTHS.grid).toBe(1);
  });

  it("should export CHART_BACKGROUNDS", () => {
    expect(CHART_BACKGROUNDS.transparent).toBe("transparent");
    expect(CHART_BACKGROUNDS.subtle).toBe("rgba(74, 93, 78, 0.05)");
  });

  it("should export CHART_PROJECTION with dotted line config", () => {
    expect(CHART_PROJECTION.borderDash).toEqual([6, 4]);
    expect(CHART_PROJECTION.borderColor).toBe("#1A1A1A");
    expect(CHART_PROJECTION.borderWidth).toBe(1);
  });

  it("CHART_ANIMATION has duration 800 and easeOutQuart easing", () => {
    expect(CHART_ANIMATION.duration).toBe(800);
    expect(CHART_ANIMATION.easing).toBe("easeOutQuart");
  });
});

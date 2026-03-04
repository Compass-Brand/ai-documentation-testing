import type { Model } from "../../api/client";

export function latencyColor(ms: number): string {
  if (ms < 100) return "text-brand-sage";
  if (ms < 500) return "text-brand-amber";
  return "text-brand-clay";
}

export function formatPrice(price: number): string {
  if (price === 0) return "Free";
  const perMillion = price * 1_000_000;
  if (perMillion < 0.01) return "<$0.01/M";
  return `$${perMillion.toFixed(2)}/M`;
}

export function formatDeployed(timestamp: number): string {
  if (!timestamp) return "\u2014";
  return new Date(timestamp * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function extractProviders(
  models: Model[],
): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const m of models) {
    const provider = m.id.split("/")[0];
    const display = provider.charAt(0).toUpperCase() + provider.slice(1);
    counts.set(display, (counts.get(display) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

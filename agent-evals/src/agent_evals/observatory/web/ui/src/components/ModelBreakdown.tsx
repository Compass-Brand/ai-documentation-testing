interface ModelBreakdownProps {
  data: Record<string, { mean_score: number; trial_count: number; cost: number }>;
}

export function ModelBreakdown({ data }: ModelBreakdownProps) {
  const sorted = Object.entries(data).sort(
    ([, a], [, b]) => b.trial_count - a.trial_count,
  );

  if (sorted.length === 0) {
    return (
      <p className="text-body-sm text-brand-slate">No model data yet.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body-sm">
        <thead>
          <tr className="border-b border-brand-mist text-left text-caption text-brand-slate">
            <th className="pb-sp-2 pr-sp-4">Model</th>
            <th className="pb-sp-2 pr-sp-4 text-right">Score</th>
            <th className="pb-sp-2 pr-sp-4 text-right">Trials</th>
            <th className="pb-sp-2 text-right">Cost</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(([model, stats]) => (
            <tr
              key={model}
              className="border-b border-brand-mist/50 text-brand-charcoal"
            >
              <td className="py-sp-2 pr-sp-4 font-medium truncate max-w-[200px]">
                {model}
              </td>
              <td className="py-sp-2 pr-sp-4 text-right tabular-nums">
                {stats.mean_score.toFixed(2)}
              </td>
              <td className="py-sp-2 pr-sp-4 text-right tabular-nums">
                {stats.trial_count}
              </td>
              <td className="py-sp-2 text-right tabular-nums">
                ${stats.cost.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

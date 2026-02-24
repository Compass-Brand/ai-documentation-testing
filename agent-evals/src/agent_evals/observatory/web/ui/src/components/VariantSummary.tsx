interface VariantSummaryProps {
  data: Record<string, { mean_score: number; trial_count: number }>;
}

export function VariantSummary({ data }: VariantSummaryProps) {
  const sorted = Object.entries(data).sort(
    ([, a], [, b]) => b.mean_score - a.mean_score,
  );

  if (sorted.length === 0) {
    return (
      <p className="text-body-sm text-brand-slate">No variant data yet.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body-sm">
        <thead>
          <tr className="border-b border-brand-mist text-left text-caption text-brand-slate">
            <th className="pb-sp-2 pr-sp-4">Variant</th>
            <th className="pb-sp-2 pr-sp-4 text-right">Score</th>
            <th className="pb-sp-2 text-right">Trials</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(([variant, stats]) => (
            <tr
              key={variant}
              className="border-b border-brand-mist/50 text-brand-charcoal"
            >
              <td className="py-sp-2 pr-sp-4 font-medium truncate max-w-[200px]">
                {variant}
              </td>
              <td className="py-sp-2 pr-sp-4 text-right tabular-nums">
                {stats.mean_score.toFixed(2)}
              </td>
              <td className="py-sp-2 text-right tabular-nums">
                {stats.trial_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

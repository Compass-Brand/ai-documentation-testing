import { useEffect, useState } from "react";

interface LastUpdatedProps {
  timestamp: Date | number | null;
}

function formatRelative(ts: Date | number): string {
  const ms = Date.now() - new Date(ts).getTime();
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export function LastUpdated({ timestamp }: LastUpdatedProps) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!timestamp) return;

    const ms = Date.now() - new Date(timestamp).getTime();
    const interval = ms < 60_000 ? 1_000 : 60_000;

    const id = setInterval(() => setTick((t) => t + 1), interval);
    return () => clearInterval(id);
  }, [timestamp]);

  if (!timestamp) {
    return <span className="text-caption text-brand-slate">--</span>;
  }

  return (
    <span className="text-caption text-brand-slate">
      {formatRelative(timestamp)}
    </span>
  );
}

import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        "text-display",
        "text-h1",
        "text-h2",
        "text-h3",
        "text-h4",
        "text-h5",
        "text-body-lg",
        "text-body",
        "text-body-sm",
        "text-caption",
        "text-data",
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** First 8 characters of a run ID */
export function shortId(id: string): string {
  return id.slice(0, 8);
}

/** Format an ISO date string as "Feb 23, 10:05 PM" */
export function formatRunDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Build a human-readable label for a run dropdown option */
export function formatRunLabel(run: {
  run_id: string;
  run_type: string;
  status: string;
  created_at: string;
}): string {
  return `${run.run_type} \u00b7 ${formatRunDate(run.created_at)} \u00b7 ${run.status} [${shortId(run.run_id)}]`;
}

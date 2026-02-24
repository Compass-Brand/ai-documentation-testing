import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { Button } from "./Button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  ctaLabel?: string;
  ctaTo?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  ctaLabel,
  ctaTo,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-sp-16 text-center">
      <Icon className="mb-sp-4 h-12 w-12 text-brand-slate" />
      <h2 className="mb-sp-2 text-h4 text-brand-charcoal">{title}</h2>
      <p className="mb-sp-6 max-w-md text-body text-brand-slate">
        {description}
      </p>
      {ctaLabel && ctaTo && (
        <Button asChild>
          <Link to={ctaTo}>{ctaLabel}</Link>
        </Button>
      )}
    </div>
  );
}

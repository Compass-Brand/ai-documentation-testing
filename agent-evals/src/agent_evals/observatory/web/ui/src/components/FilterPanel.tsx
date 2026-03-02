import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { cn } from "../lib/utils";
import type { ReactNode } from "react";

interface FilterSectionProps {
  label: string;
  children: ReactNode;
}

export function FilterSection({ label, children }: FilterSectionProps) {
  return (
    <div className="mb-sp-6">
      <h4 className="mb-sp-3 text-body-sm font-medium text-brand-charcoal">
        {label}
      </h4>
      {children}
    </div>
  );
}

interface FilterCheckboxProps {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

export function FilterCheckbox({
  label,
  checked,
  onCheckedChange,
}: FilterCheckboxProps) {
  return (
    <label className="flex cursor-pointer items-center gap-sp-3 py-sp-1 text-body-sm text-brand-slate hover:text-brand-charcoal transition-colors duration-micro">
      <Checkbox.Root
        checked={checked}
        onCheckedChange={(c) => onCheckedChange(c === true)}
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded border",
          "border-brand-mist transition-colors duration-micro",
          "focus-visible:ring-2 focus-visible:ring-brand-goldenrod",
          "focus-visible:ring-offset-2",
          "data-[state=checked]:bg-brand-goldenrod",
          "data-[state=checked]:border-brand-goldenrod",
        )}
      >
        <Checkbox.Indicator>
          <Check className="h-3.5 w-3.5 text-brand-charcoal" />
        </Checkbox.Indicator>
      </Checkbox.Root>
      {label}
    </label>
  );
}

interface FilterRangeProps {
  label: string;
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  format?: (n: number) => string;
}

export function FilterRange({
  label,
  min,
  max,
  value,
  onChange,
  format,
}: FilterRangeProps) {
  const fmt = format ?? String;
  const inputId = `filter-range-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="mb-sp-4">
      <label htmlFor={inputId} className="mb-sp-1 block text-caption font-medium text-brand-charcoal">
        {label}
      </label>
      <div className="flex justify-between text-caption text-brand-slate mb-sp-2">
        <span>{fmt(value[0])}</span>
        <span>{fmt(value[1])}</span>
      </div>
      <input
        id={inputId}
        type="range"
        min={min}
        max={max}
        value={value[1]}
        onChange={(e) => onChange([value[0], parseInt(e.target.value)])}
        className="w-full accent-brand-goldenrod"
        aria-label={label}
      />
    </div>
  );
}

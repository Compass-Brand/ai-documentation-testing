import * as Checkbox from "@radix-ui/react-checkbox";
import { motion } from "framer-motion";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import { type ReactNode, useCallback, useRef, useState } from "react";

interface FilterSectionProps {
  label: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function FilterSection({ label, children, defaultOpen = true }: FilterSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="mb-sp-6">
      <button
        className="flex items-center justify-between w-full mb-sp-3 text-body-sm font-medium text-brand-charcoal hover:text-brand-goldenrod transition-colors duration-micro"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        {label}
        <ChevronDown className={cn(
          "h-4 w-4 transition-transform duration-micro",
          isOpen && "rotate-180"
        )} />
      </button>
      {isOpen && children}
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

const FILL_SPRING = { type: "spring", stiffness: 300, damping: 30 } as const;

export function FilterRange({
  label,
  min,
  max,
  value,
  onChange,
  format,
}: FilterRangeProps) {
  const fmt = format ?? String;
  const baseId = `filter-range-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const trackRef = useRef<HTMLDivElement>(null);

  const range = max - min || 1;
  const lowPct = ((value[0] - min) / range) * 100;
  const highPct = ((value[1] - min) / range) * 100;

  const handleLow = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = parseInt(e.target.value);
      onChange([Math.min(next, value[1]), value[1]]);
    },
    [onChange, value],
  );

  const handleHigh = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = parseInt(e.target.value);
      onChange([value[0], Math.max(next, value[0])]);
    },
    [onChange, value],
  );

  return (
    <div className="mb-sp-4">
      <label
        htmlFor={`${baseId}-low`}
        className="mb-sp-1 block text-caption font-medium text-brand-charcoal"
      >
        {label}
      </label>
      <div className="flex justify-between text-caption text-brand-slate mb-sp-2">
        <span>{fmt(value[0])}</span>
        <span>{fmt(value[1])}</span>
      </div>

      {/* Dual-range track container */}
      <div ref={trackRef} className="dual-range relative h-5 w-full">
        {/* Background track */}
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-brand-mist" />

        {/* Animated fill bar */}
        <motion.div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-brand-goldenrod"
          style={{ left: `${lowPct}%` }}
          animate={{ width: `${highPct - lowPct}%` }}
          transition={FILL_SPRING}
        />

        {/* Low thumb */}
        <input
          id={`${baseId}-low`}
          type="range"
          min={min}
          max={max}
          value={value[0]}
          onChange={handleLow}
          className="dual-range-thumb pointer-events-none absolute inset-0 w-full"
          aria-label={`${label} minimum`}
        />

        {/* High thumb */}
        <input
          id={`${baseId}-high`}
          type="range"
          min={min}
          max={max}
          value={value[1]}
          onChange={handleHigh}
          className="dual-range-thumb pointer-events-none absolute inset-0 w-full"
          aria-label={`${label} maximum`}
        />
      </div>
    </div>
  );
}

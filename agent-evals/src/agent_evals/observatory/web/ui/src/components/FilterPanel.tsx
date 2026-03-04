import * as Checkbox from "@radix-ui/react-checkbox";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

interface FilterSectionProps {
  label: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export function FilterSection({ label, children, defaultOpen = true }: FilterSectionProps) {
  const [isOpen, setIsOpen] = useState(() => defaultOpen);

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
  const debounceTimer = useRef<ReturnType<typeof setTimeout>>();

  // Local state for instant visual feedback; debounce parent callback.
  // Use a key derived from the prop to reset local state when the prop changes,
  // avoiding both useEffect sync and ref access during render.
  const [localValue, setLocalValue] = useState(() => value);
  const [trackedValue, setTrackedValue] = useState(() => value);
  if (trackedValue[0] !== value[0] || trackedValue[1] !== value[1]) {
    setTrackedValue(value);
    setLocalValue(value);
  }

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => clearTimeout(debounceTimer.current);
  }, []);

  const range = max - min || 1;
  const lowPct = ((localValue[0] - min) / range) * 100;
  const highPct = ((localValue[1] - min) / range) * 100;

  const handleLow = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = parseInt(e.target.value);
      const newVal: [number, number] = [Math.min(next, localValue[1]), localValue[1]];
      setLocalValue(newVal);
      clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => onChange(newVal), 150);
    },
    [localValue, onChange],
  );

  const handleHigh = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = parseInt(e.target.value);
      const newVal: [number, number] = [localValue[0], Math.max(next, localValue[0])];
      setLocalValue(newVal);
      clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => onChange(newVal), 150);
    },
    [localValue, onChange],
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
        <span>{fmt(localValue[0])}</span>
        <span>{fmt(localValue[1])}</span>
      </div>

      {/* Dual-range track container */}
      <div ref={trackRef} className="dual-range relative h-5 w-full">
        {/* Background track */}
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-brand-mist" />

        {/* Fill bar */}
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-brand-goldenrod transition-all duration-150"
          style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
        />

        {/* Low thumb */}
        <input
          id={`${baseId}-low`}
          type="range"
          min={min}
          max={max}
          value={localValue[0]}
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
          value={localValue[1]}
          onChange={handleHigh}
          className="dual-range-thumb pointer-events-none absolute inset-0 w-full"
          aria-label={`${label} maximum`}
        />
      </div>
    </div>
  );
}

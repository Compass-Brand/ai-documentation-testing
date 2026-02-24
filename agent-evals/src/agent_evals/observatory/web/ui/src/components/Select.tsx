import * as SelectPrimitive from "@radix-ui/react-select";
import { ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  options: SelectOption[];
  value: string;
  onValueChange: (v: string) => void;
  placeholder?: string;
  "aria-label"?: string;
}

export function Select({
  options,
  value,
  onValueChange,
  placeholder = "Select...",
  "aria-label": ariaLabel,
}: SelectProps) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger
        aria-label={ariaLabel}
        className={cn(
          "inline-flex h-11 w-full items-center justify-between gap-sp-2",
          "rounded-card border border-brand-mist bg-brand-bone px-sp-4 py-sp-2",
          "text-body-sm text-brand-charcoal",
          "focus:outline-none focus:ring-2 focus:ring-brand-goldenrod focus:ring-offset-2",
          "transition-colors duration-micro",
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon>
          <ChevronDown className="h-4 w-4 text-brand-slate" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className={cn(
            "z-50 max-h-60 overflow-auto rounded-card border border-brand-mist",
            "bg-brand-bone shadow-panel",
            "animate-fade-in-up",
          )}
        >
          <SelectPrimitive.Viewport className="p-sp-1">
            {options.map((opt) => (
              <SelectPrimitive.Item
                key={opt.value}
                value={opt.value}
                className={cn(
                  "relative cursor-pointer rounded px-sp-4 py-sp-2 text-body-sm text-brand-charcoal",
                  "outline-none",
                  "data-[highlighted]:bg-brand-goldenrod/10 data-[highlighted]:text-brand-charcoal",
                  "data-[state=checked]:font-medium",
                )}
              >
                <SelectPrimitive.ItemText>
                  {opt.label}
                </SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

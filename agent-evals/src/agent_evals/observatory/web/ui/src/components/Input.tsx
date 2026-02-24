import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-11 w-full rounded-card border border-brand-mist bg-brand-bone",
      "px-sp-4 py-sp-3 text-body text-brand-charcoal",
      "placeholder:text-brand-slate/60",
      "focus:border-brand-goldenrod focus:outline-none focus:ring-2",
      "focus:ring-brand-goldenrod/20",
      "disabled:opacity-50 disabled:cursor-not-allowed",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

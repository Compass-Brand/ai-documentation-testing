import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center font-medium",
    "transition-all duration-micro ease-out",
    "focus-visible:outline-none focus-visible:ring-2",
    "focus-visible:ring-brand-goldenrod focus-visible:ring-offset-2",
    "disabled:opacity-50 disabled:pointer-events-none",
  ].join(" "),
  {
    variants: {
      variant: {
        primary: [
          "bg-brand-goldenrod text-brand-charcoal rounded-pill",
          "hover:brightness-105 hover:shadow-card-hover hover:-translate-y-px",
          "active:translate-y-0 active:brightness-95",
        ].join(" "),
        secondary: [
          "bg-transparent text-brand-charcoal border border-brand-charcoal rounded-pill",
          "hover:bg-brand-cream",
        ].join(" "),
        ghost:
          "text-brand-slate hover:text-brand-charcoal hover:bg-brand-cream rounded-card",
        danger: [
          "bg-brand-clay text-brand-bone rounded-pill",
          "hover:brightness-110 hover:shadow-card-hover hover:-translate-y-px",
          "active:translate-y-0 active:brightness-95",
        ].join(" "),
      },
      size: {
        sm: "h-8 px-sp-4 text-body-sm",
        md: "h-11 px-sp-6 text-body",
        lg: "h-[52px] px-sp-8 text-body-lg",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

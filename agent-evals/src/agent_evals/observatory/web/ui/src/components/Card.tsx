import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

const cardVariants = cva(
  "bg-brand-bone rounded-card p-sp-6 shadow-card transition-shadow duration-state",
  {
    variants: {
      variant: {
        default: "hover:shadow-card-hover",
        interactive: [
          "cursor-pointer hover:shadow-card-hover",
          "hover:ring-1 hover:ring-brand-goldenrod/20",
        ].join(" "),
        stat: "border-l-4 border-brand-goldenrod",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface CardProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, className }))}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("mb-sp-4", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<
  HTMLHeadingElement,
  HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-h4 text-brand-charcoal", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("text-body text-brand-slate", className)}
      {...props}
    />
  ),
);
CardContent.displayName = "CardContent";

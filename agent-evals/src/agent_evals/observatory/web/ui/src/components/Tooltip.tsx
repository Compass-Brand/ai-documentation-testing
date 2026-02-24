import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "../lib/utils";

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

export function Tooltip({ children, content, side = "top" }: TooltipProps) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className={cn(
            "z-50 rounded-card px-sp-3 py-sp-2",
            "bg-brand-goldenrod text-brand-bone text-caption",
            "shadow-card animate-fade-in-up",
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-brand-goldenrod" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export const TooltipProvider = TooltipPrimitive.Provider;

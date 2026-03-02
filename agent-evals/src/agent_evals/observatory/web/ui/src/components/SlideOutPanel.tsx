import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "../lib/utils";
import type { ReactNode } from "react";

interface SlideOutPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: "md" | "lg";
}

const widthClasses = {
  md: "w-[400px]",
  lg: "w-[500px]",
};

export function SlideOutPanel({
  open,
  onClose,
  title,
  children,
  width = "lg",
}: SlideOutPanelProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-brand-charcoal/30 transition-opacity duration-modal" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            "fixed right-0 top-0 h-full bg-brand-bone shadow-panel",
            "overflow-y-auto",
            "transition-transform duration-page ease-in-out",
            "data-[state=open]:translate-x-0",
            "data-[state=closed]:translate-x-full",
            widthClasses[width],
          )}
        >
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-brand-mist bg-brand-bone px-sp-6 py-sp-4">
            <Dialog.Title className="text-h4 text-brand-charcoal">
              {title}
            </Dialog.Title>
            <Dialog.Close className="rounded-card p-sp-2 text-brand-slate hover:bg-brand-cream hover:text-brand-charcoal transition-colors duration-micro focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <div className="p-sp-6">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "../lib/utils";

interface ShortcutHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const shortcuts = [
  { keys: "g r", description: "Go to Run Config" },
  { keys: "g l", description: "Go to Live Monitor" },
  { keys: "g e", description: "Go to Results Explorer" },
  { keys: "g o", description: "Go to Observatory" },
  { keys: "g h", description: "Go to History" },
  { keys: "g p", description: "Go to Pipeline" },
  { keys: "g m", description: "Go to Models" },
  { keys: "?", description: "Show this help" },
];

export function ShortcutHelp({ open, onOpenChange }: ShortcutHelpProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-brand-charcoal/50" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
            "w-full max-w-md rounded-card bg-brand-bone p-sp-8 shadow-panel",
            "animate-fade-in-up",
          )}
        >
          <div className="mb-sp-6 flex items-center justify-between">
            <Dialog.Title className="text-h4 text-brand-charcoal">
              Keyboard Shortcuts
            </Dialog.Title>
            <Dialog.Close
              className="rounded-card p-sp-1 text-brand-slate hover:text-brand-charcoal transition-colors duration-micro"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>

          <div className="space-y-sp-3">
            {shortcuts.map((s) => (
              <div
                key={s.keys}
                className="flex items-center justify-between text-body-sm"
              >
                <span className="text-brand-slate">{s.description}</span>
                <span className="flex gap-sp-1">
                  {s.keys.split(" ").map((key) => (
                    <kbd
                      key={key}
                      className={cn(
                        "inline-flex h-6 min-w-[24px] items-center justify-center",
                        "rounded border border-brand-mist bg-brand-cream",
                        "px-sp-2 font-mono text-caption text-brand-charcoal",
                      )}
                    >
                      {key}
                    </kbd>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

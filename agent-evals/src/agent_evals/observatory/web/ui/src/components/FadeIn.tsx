import { cn } from "../lib/utils";

interface FadeInProps {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}

export function FadeIn({ children, delay = 0, className }: FadeInProps) {
  return (
    <div
      className={cn("animate-fade-in-up opacity-0", className)}
      style={{
        animationDelay: `${delay * 50}ms`,
        animationFillMode: "forwards",
      }}
    >
      {children}
    </div>
  );
}

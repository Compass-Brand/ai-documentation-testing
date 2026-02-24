import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

const CHORD_TIMEOUT = 800;

const NAV_CHORDS: Record<string, string> = {
  r: "/",
  l: "/live",
  e: "/results",
  o: "/observatory",
  h: "/history",
  p: "/pipeline",
  m: "/models",
};

export function useKeyboardShortcuts(onHelpOpen?: () => void) {
  const navigate = useNavigate();
  const [pendingG, setPendingG] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable;

      if (isInput) return;

      if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        onHelpOpen?.();
        return;
      }

      if (pendingG) {
        setPendingG(false);
        if (timerRef.current) clearTimeout(timerRef.current);
        const dest = NAV_CHORDS[e.key];
        if (dest) {
          e.preventDefault();
          navigate(dest);
        }
        return;
      }

      if (e.key === "g" && !e.ctrlKey && !e.metaKey) {
        setPendingG(true);
        timerRef.current = setTimeout(() => setPendingG(false), CHORD_TIMEOUT);
      }
    },
    [navigate, onHelpOpen, pendingG],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return { pendingG };
}

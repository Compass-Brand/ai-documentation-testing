import { m, useMotionValue, useSpring, animate } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../lib/utils";

interface CustomScrollbarProps {
  children: React.ReactNode;
  scrollRef: React.RefObject<HTMLDivElement>;
  selectedPositions?: number[];
  className?: string;
}

const FADE_DELAY_MS = 1500;
const THUMB_MIN_HEIGHT = 24;

const SPRING_CONFIG = { stiffness: 300, damping: 30 };

const EMPTY_POSITIONS: number[] = [];

export function CustomScrollbar({
  children,
  scrollRef,
  selectedPositions = EMPTY_POSITIONS,
  className,
}: CustomScrollbarProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const fadeTimer = useRef<ReturnType<typeof setTimeout>>();

  const [thumbRatio, setThumbRatio] = useState(1);
  const [trackHeight, setTrackHeight] = useState(0);

  const rawY = useMotionValue(0);
  const springY = useSpring(rawY, SPRING_CONFIG);
  const opacity = useMotionValue(0);

  const thumbHeight = Math.max(thumbRatio * trackHeight, THUMB_MIN_HEIGHT);

  const showThumb = useCallback(() => {
    animate(opacity, 1, { duration: 0.15 });
    clearTimeout(fadeTimer.current);
    fadeTimer.current = setTimeout(() => {
      if (!isDragging.current) {
        animate(opacity, 0, { duration: 0.3 });
      }
    }, FADE_DELAY_MS);
  }, [opacity]);

  const syncThumbToScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;

    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) return;

    const fraction = el.scrollTop / scrollable;
    const maxY = trackHeight - thumbHeight;
    rawY.set(fraction * maxY);
  }, [scrollRef, trackHeight, thumbHeight, rawY]);

  /* --- observe container dimensions --- */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const measure = () => {
      const ratio = el.clientHeight / el.scrollHeight;
      setThumbRatio(Math.min(ratio, 1));
      setTrackHeight(el.clientHeight);
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [scrollRef]);

  /* --- listen for scroll events --- */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const onScroll = () => {
      syncThumbToScroll();
      showThumb();
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [scrollRef, syncThumbToScroll, showThumb]);

  /* --- thumb drag handlers --- */
  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      isDragging.current = true;
      showThumb();

      const startY = e.clientY;
      const startTop = rawY.get();
      const maxY = trackHeight - thumbHeight;

      const onMove = (ev: PointerEvent) => {
        const delta = ev.clientY - startY;
        const nextY = Math.max(0, Math.min(maxY, startTop + delta));
        rawY.set(nextY);

        const el = scrollRef.current;
        if (el) {
          const scrollable = el.scrollHeight - el.clientHeight;
          el.scrollTop = (nextY / maxY) * scrollable;
        }
      };

      const onUp = () => {
        isDragging.current = false;
        showThumb();
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [rawY, trackHeight, thumbHeight, scrollRef, showThumb],
  );

  /* hide when content fits without scroll */
  if (thumbRatio >= 1) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div className={cn("relative", className)}>
      {children}

      {/* track */}
      <m.div
        ref={trackRef}
        className="absolute right-0 top-0 z-20 w-[10px] rounded-full"
        style={{ height: trackHeight || "100%", opacity }}
      >
        {/* mini-map dots */}
        {selectedPositions.map((pos) => (
          <div
            key={`pos-${pos.toFixed(6)}`}
            className="absolute left-1/2 h-[3px] w-[3px] -translate-x-1/2 rounded-full"
            style={{
              top: `${pos * 100}%`,
              backgroundColor: "#C2A676",
              opacity: 0.4,
            }}
          />
        ))}

        {/* thumb */}
        <m.div
          className="absolute left-1/2 w-[6px] -translate-x-1/2 cursor-grab rounded-full active:cursor-grabbing"
          style={{
            y: springY,
            height: thumbHeight,
            backgroundColor: "rgba(194, 166, 118, 0.6)",
          }}
          whileHover={{
            backgroundColor: "rgba(194, 166, 118, 1)",
            boxShadow: "0 0 8px rgba(194, 166, 118, 0.5)",
          }}
          transition={{ duration: 0.15 }}
          onPointerDown={onPointerDown}
        />
      </m.div>
    </div>
  );
}

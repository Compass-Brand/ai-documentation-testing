import { useEffect, useRef } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";

const SPRING_CONFIG = { stiffness: 500, damping: 35 };
const GLOW_SIZE = 220;

export function CursorGlow() {
  const mouseX = useMotionValue(-GLOW_SIZE);
  const mouseY = useMotionValue(-GLOW_SIZE);
  const springX = useSpring(mouseX, SPRING_CONFIG);
  const springY = useSpring(mouseY, SPRING_CONFIG);
  const pending = useRef(false);
  const latestEvent = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      latestEvent.current = { x: e.clientX - GLOW_SIZE / 2, y: e.clientY - GLOW_SIZE / 2 };
      if (!pending.current) {
        pending.current = true;
        requestAnimationFrame(() => {
          mouseX.set(latestEvent.current.x);
          mouseY.set(latestEvent.current.y);
          pending.current = false;
        });
      }
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY]);

  return (
    <motion.div
      className="fixed pointer-events-none"
      style={{
        x: springX,
        y: springY,
        width: GLOW_SIZE,
        height: GLOW_SIZE,
        background:
          "radial-gradient(circle, rgba(194, 166, 118, 0.12) 0%, transparent 70%)",
        zIndex: 9999,
      }}
      aria-hidden="true"
    />
  );
}

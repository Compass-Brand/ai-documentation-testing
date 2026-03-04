import { useEffect } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";

const SPRING_CONFIG = { stiffness: 300, damping: 30 };
const GLOW_SIZE = 250;

export function CursorGlow() {
  const mouseX = useMotionValue(-GLOW_SIZE);
  const mouseY = useMotionValue(-GLOW_SIZE);
  const springX = useSpring(mouseX, SPRING_CONFIG);
  const springY = useSpring(mouseY, SPRING_CONFIG);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX - GLOW_SIZE / 2);
      mouseY.set(e.clientY - GLOW_SIZE / 2);
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
          "radial-gradient(circle, rgba(194, 166, 118, 0.2) 0%, transparent 70%)",
        zIndex: 9999,
      }}
      aria-hidden="true"
    />
  );
}

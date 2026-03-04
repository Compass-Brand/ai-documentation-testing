import { useEffect, useMemo } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

interface Particle {
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
}

function generateParticles(count: number): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    const seed = (i + 1) * 7919;
    const x = (seed * 13) % 100;
    const y = (seed * 17) % 100;
    const size = 3 + ((seed * 23) % 5);
    const duration = 15 + ((seed * 29) % 25);
    const delay = (seed * 31) % 10;
    particles.push({ x, y, size, duration, delay });
  }
  return particles;
}

const SPRING = { stiffness: 40, damping: 20 };

export function AmbientBackground() {
  const particles = useMemo(() => generateParticles(18), []);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, SPRING);
  const springY = useSpring(mouseY, SPRING);

  // Parallax transforms — lines shift opposite to mouse for depth
  const lineX = useTransform(springX, [0, 1], [0, -30]);
  const lineY = useTransform(springY, [0, 1], [0, -15]);

  // Gradient follows mouse subtly
  const gradX = useTransform(springX, [0, 1], [20, 40]);
  const gradY = useTransform(springY, [0, 1], [10, 30]);
  const gradBg = useTransform(
    [gradX, gradY],
    ([x, y]: number[]) =>
      `radial-gradient(ellipse at ${x}% ${y}%, rgba(163, 133, 82, 0.3) 0%, transparent 70%)`,
  );

  useEffect(() => {
    const handleMouse = (e: MouseEvent) => {
      mouseX.set(e.clientX / window.innerWidth);
      mouseY.set(e.clientY / window.innerHeight);
    };
    window.addEventListener("mousemove", handleMouse, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouse);
  }, [mouseX, mouseY]);

  return (
    <>
      {/* Gradient mesh — follows mouse, behind content */}
      <motion.div
        className="fixed inset-0 pointer-events-none"
        style={{ zIndex: -1, background: gradBg }}
        aria-hidden="true"
      />

      {/* Topo contour lines — ABOVE backgrounds, pointer-events-none */}
      <motion.svg
        className="fixed inset-0 w-full h-full pointer-events-none"
        style={{ zIndex: 1, x: lineX, y: lineY }}
        aria-hidden="true"
        preserveAspectRatio="none"
        viewBox="0 0 1600 900"
      >
        <g className="animate-[drift_60s_linear_infinite]" opacity="0.12">
          <path
            d="M-200,60 Q50,20 250,70 T650,50 T1050,70 T1450,50 T1850,70"
            stroke="#9A7B4F"
            strokeWidth="1.5"
            fill="none"
          />
          <path
            d="M-200,160 Q100,110 300,170 T700,150 T1100,170 T1500,150 T1900,170"
            stroke="#9A7B4F"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M-200,280 Q80,230 280,290 T680,270 T1080,290 T1480,270 T1880,290"
            stroke="#9A7B4F"
            strokeWidth="1.5"
            fill="none"
          />
          <path
            d="M-200,380 Q150,320 350,390 T750,370 T1150,390 T1550,370 T1950,390"
            stroke="#9A7B4F"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M-200,480 Q100,430 300,490 T700,470 T1100,490 T1500,470 T1900,490"
            stroke="#9A7B4F"
            strokeWidth="1.5"
            fill="none"
          />
          <path
            d="M-200,580 Q200,520 400,590 T800,570 T1200,590 T1600,570 T2000,590"
            stroke="#9A7B4F"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M-200,680 Q120,630 320,690 T720,670 T1120,690 T1520,670 T1920,690"
            stroke="#9A7B4F"
            strokeWidth="1.5"
            fill="none"
          />
          <path
            d="M-200,770 Q180,720 380,780 T780,760 T1180,780 T1580,760 T1980,780"
            stroke="#9A7B4F"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M-200,850 Q60,810 260,860 T660,840 T1060,860 T1460,840 T1860,860"
            stroke="#9A7B4F"
            strokeWidth="1.5"
            fill="none"
          />
        </g>
      </motion.svg>

      {/* Floating particles — above backgrounds */}
      <div
        className="fixed inset-0 pointer-events-none overflow-hidden"
        style={{ zIndex: 1 }}
        aria-hidden="true"
      >
        {particles.map((p, i) => (
          <div
            key={i}
            className="absolute rounded-full"
            style={{
              width: p.size,
              height: p.size,
              left: `${p.x}%`,
              top: `${p.y}%`,
              backgroundColor: "#9A7B4F",
              opacity: 0.25,
              animation: `float-${i % 3} ${p.duration}s ease-in-out infinite`,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}
      </div>
    </>
  );
}

import { useMemo } from "react";

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
    // Deterministic pseudo-random using a simple seed approach
    const seed = (i + 1) * 7919;
    const x = ((seed * 13) % 100);
    const y = ((seed * 17) % 100);
    const size = 2 + ((seed * 23) % 4);
    const duration = 15 + ((seed * 29) % 25);
    const delay = ((seed * 31) % 10);
    particles.push({ x, y, size, duration, delay });
  }
  return particles;
}

export function AmbientBackground() {
  const particles = useMemo(() => generateParticles(18), []);

  return (
    <div
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: -1 }}
      aria-hidden="true"
    >
      {/* Gradient mesh */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 30% 20%, rgba(194, 166, 118, 0.05) 0%, transparent 70%)",
        }}
      />

      {/* Topographic contour lines */}
      <svg
        className="absolute inset-0 w-full h-full"
        style={{ opacity: 0.03 }}
      >
        <g className="animate-[drift_60s_linear_infinite]">
          <path
            d="M-100,200 Q100,100 300,200 T700,200 T1100,200 T1500,200"
            stroke="#C2A676"
            strokeWidth="1"
            fill="none"
          />
          <path
            d="M-100,300 Q200,200 400,300 T800,300 T1200,300 T1600,300"
            stroke="#C2A676"
            strokeWidth="0.5"
            fill="none"
          />
          <path
            d="M-100,400 Q150,300 350,400 T750,400 T1150,400 T1550,400"
            stroke="#C2A676"
            strokeWidth="0.5"
            fill="none"
          />
          <path
            d="M-100,500 Q250,400 450,500 T850,500 T1250,500 T1650,500"
            stroke="#C2A676"
            strokeWidth="1"
            fill="none"
          />
        </g>
      </svg>

      {/* Floating particles */}
      {particles.map((p, i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: p.size,
            height: p.size,
            left: `${p.x}%`,
            top: `${p.y}%`,
            backgroundColor: "#C2A676",
            opacity: 0.04,
            animation: `float-${i % 3} ${p.duration}s ease-in-out infinite`,
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </div>
  );
}

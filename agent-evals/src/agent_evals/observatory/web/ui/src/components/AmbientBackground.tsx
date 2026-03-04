import { useEffect, useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

const SPRING = { stiffness: 40, damping: 20 };
const NUM_RINGS = 18;
const PTS = 64;
const RING_GAP = 45;
const RING_GROWTH = 0.10;
const COLOR = [154, 123, 79]; // #9A7B4F

/* ── Compact 2D Perlin noise (no deps) ─────────────────────────── */
function createNoise(seed = 42) {
  const p = new Uint8Array(512);
  for (let i = 0; i < 256; i++) p[i] = i;
  let s = seed;
  for (let i = 255; i > 0; i--) {
    s = (s * 16807 + 1) & 0x7fffffff;
    const j = s % (i + 1);
    [p[i], p[j]] = [p[j], p[i]];
  }
  for (let i = 0; i < 256; i++) p[i + 256] = p[i];

  const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
  const lerp = (a: number, b: number, t: number) => a + t * (b - a);
  const grad = (h: number, x: number, y: number) => {
    const k = h & 3;
    return ((k & 1) ? -x : x) + ((k & 2) ? -y : y);
  };

  return (x: number, y: number) => {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    const xf = x - Math.floor(x);
    const yf = y - Math.floor(y);
    const u = fade(xf);
    const v = fade(yf);
    return lerp(
      lerp(grad(p[p[X] + Y], xf, yf), grad(p[p[X + 1] + Y], xf - 1, yf), u),
      lerp(
        grad(p[p[X] + Y + 1], xf, yf - 1),
        grad(p[p[X + 1] + Y + 1], xf - 1, yf - 1),
        u,
      ),
      v,
    );
  };
}

/* ── Smooth closed curve via quadratic-bezier midpoint technique ── */
function drawSmooth(ctx: CanvasRenderingContext2D, pts: [number, number][]) {
  if (pts.length < 3) return;
  const mid = (a: [number, number], b: [number, number]): [number, number] =>
    [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const start = mid(pts[pts.length - 1], pts[0]);
  ctx.moveTo(start[0], start[1]);
  for (let i = 0; i < pts.length; i++) {
    const m = mid(pts[i], pts[(i + 1) % pts.length]);
    ctx.quadraticCurveTo(pts[i][0], pts[i][1], m[0], m[1]);
  }
  ctx.closePath();
}

/**
 * Ambient background with three layers:
 * 1. Mouse-reactive gradient mesh (z-index: -1)
 * 2. Canvas topo contours centered on [data-compass-rose] element (z-index: 0)
 *    - Tracks compass position via getBoundingClientRect (scroll-aware)
 *    - 14 rings with non-linear spacing covering full viewport
 *    - Perlin noise + traveling waves for constant organic motion
 *    - Subtle cursor ripple (pond effect)
 * 3. Floating particles (z-index: 0)
 *
 * Content wrappers need `relative z-[1]` to sit above the topo layer.
 */
export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -9999, y: -9999 });
  const animRef = useRef(0);
  const lastFrameTime = useRef(0);
  const compassRectRef = useRef<DOMRect | null>(null);
  const mousePending = useRef(false);

  /* Gradient mesh spring values */
  const mouseX = useMotionValue(0.3);
  const mouseY = useMotionValue(0.2);
  const springX = useSpring(mouseX, SPRING);
  const springY = useSpring(mouseY, SPRING);
  const gradBg = useTransform(
    [springX, springY],
    ([x, y]: number[]) =>
      `radial-gradient(ellipse at ${(x as number) * 100}% ${(y as number) * 100}%, rgba(163,133,82,0.20) 0%, transparent 60%)`,
  );

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const noise = createNoise();
    let t = 0;

    /* Cache compass element ref (queried once) */
    let compassEl: Element | null = null;
    const findCompass = () => {
      compassEl = document.querySelector("[data-compass-rose]");
      if (compassEl) {
        compassRectRef.current = compassEl.getBoundingClientRect();
      }
    };
    findCompass();
    /* Re-query after a short delay in case the DOM hasn't rendered yet */
    const retryTimer = setTimeout(findCompass, 500);

    /* Update cached compass bounding rect */
    const updateCompassRect = () => {
      if (compassEl) {
        compassRectRef.current = compassEl.getBoundingClientRect();
      }
    };

    let resizeScrollTimer: ReturnType<typeof setTimeout> | undefined;
    const throttledRectUpdate = () => {
      clearTimeout(resizeScrollTimer);
      resizeScrollTimer = setTimeout(updateCompassRect, 100);
    };

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      updateCompassRect();
    };
    resize();

    const onMouse = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
      if (!mousePending.current) {
        mousePending.current = true;
        requestAnimationFrame(() => {
          mouseX.set(mouseRef.current.x / window.innerWidth);
          mouseY.set(mouseRef.current.y / window.innerHeight);
          mousePending.current = false;
        });
      }
    };

    window.addEventListener("resize", resize);
    window.addEventListener("scroll", throttledRectUpdate, { passive: true });
    window.addEventListener("mousemove", onMouse, { passive: true });

    const draw = () => {
      /* Throttle to ~30fps */
      const now = performance.now();
      if (now - lastFrameTime.current < 33) {
        animRef.current = requestAnimationFrame(draw);
        return;
      }
      lastFrameTime.current = now;

      t += 0.012;
      const w = window.innerWidth;
      const h = window.innerHeight;

      /* Track compass center via cached rect — scroll-aware */
      let cx = Math.min(156, w * 0.12);
      let cy = h * 0.5;
      const rect = compassRectRef.current;
      if (rect) {
        cx = rect.left + rect.width / 2;
        cy = rect.top + rect.height / 2;
      }

      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      const compassRot = t * 0.22;

      ctx.clearRect(0, 0, w, h);

      for (let ring = 0; ring < NUM_RINGS; ring++) {
        const baseR = (ring + 1) * RING_GAP * (1 + ring * RING_GROWTH);
        const alpha = Math.max(0.08, 0.22 - ring * 0.008);
        const lw = Math.max(0.7, 1.8 - ring * 0.05);

        const pts: [number, number][] = [];

        for (let i = 0; i < PTS; i++) {
          const angle = (i / PTS) * Math.PI * 2;
          const coupled = angle + compassRot * 0.05 / (ring + 1);

          /* Multi-octave noise → organic shape */
          const n1 = noise(
            Math.cos(coupled) * 1.5 + t * 0.8 + ring * 0.5,
            Math.sin(coupled) * 1.5 + t * 0.6 + ring * 0.5,
          );
          const n2 = noise(
            Math.cos(coupled) * 3 + t * 0.5 + ring * 1.2,
            Math.sin(coupled) * 3 - t * 0.3 + ring * 1.2,
          );
          const organic = (n1 * 20 + n2 * 10) * (1 + ring * 0.15);

          /* Traveling waves along contour (flowing-water feel) */
          const wave =
            Math.sin(angle * 3 + t * 2.5) * 12 * (1 + ring * 0.12) +
            Math.sin(angle * 5 - t * 1.5) * 6;

          /* Compass pulse: outward-propagating ripple, scales with ring */
          const pulse = Math.sin(baseR * 0.01 - t * 3) * (10 + ring * 2);

          const r = baseR + organic + wave + pulse;
          let px = cx + Math.cos(angle) * r;
          let py = cy + Math.sin(angle) * r;

          /* Subtle cursor ripple */
          const dx = px - mx;
          const dy = py - my;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const maxInfl = 250;
          if (dist < maxInfl && dist > 1) {
            const falloff = (1 - dist / maxInfl) ** 2;
            const ripple = Math.sin(dist * 0.03 - t * 4) * 12 * falloff;
            px += (dx / dist) * ripple;
            py += (dy / dist) * ripple;
          }

          pts.push([px, py]);
        }

        ctx.beginPath();
        ctx.strokeStyle = `rgba(${COLOR[0]},${COLOR[1]},${COLOR[2]},${alpha})`;
        ctx.lineWidth = lw;
        drawSmooth(ctx, pts);
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    /* Pause animation when tab is not visible */
    const handleVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(animRef.current);
      } else {
        lastFrameTime.current = 0;
        animRef.current = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      cancelAnimationFrame(animRef.current);
      clearTimeout(retryTimer);
      clearTimeout(resizeScrollTimer);
      window.removeEventListener("resize", resize);
      window.removeEventListener("scroll", throttledRectUpdate);
      window.removeEventListener("mousemove", onMouse);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [mouseX, mouseY]);

  return (
    <>
      {/* Layer 1: Mouse-reactive gradient mesh */}
      <motion.div
        className="fixed inset-0 pointer-events-none"
        style={{ zIndex: -1, background: gradBg }}
        aria-hidden="true"
      />

      {/* Layer 2: Canvas topo contour lines — behind content */}
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none"
        style={{ zIndex: 0, willChange: 'transform' }}
        aria-hidden="true"
      />

      {/* Layer 3: Floating particles */}
      <div
        className="fixed inset-0 pointer-events-none overflow-hidden"
        style={{ zIndex: 0 }}
        aria-hidden="true"
      >
        {Array.from({ length: 12 }, (_, i) => {
          const seed = (i + 1) * 7919;
          return (
            <div
              key={i}
              className="absolute rounded-full"
              style={{
                width: 3 + ((seed * 23) % 4),
                height: 3 + ((seed * 23) % 4),
                left: `${(seed * 13) % 100}%`,
                top: `${(seed * 17) % 100}%`,
                backgroundColor: "#9A7B4F",
                opacity: 0.2,
                animation: `float-${i % 3} ${18 + ((seed * 29) % 22)}s ease-in-out infinite`,
                animationDelay: `${(seed * 31) % 10}s`,
                willChange: 'transform',
              }}
            />
          );
        })}
      </div>
    </>
  );
}

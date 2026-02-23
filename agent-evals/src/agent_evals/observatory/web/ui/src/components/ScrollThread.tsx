import { useState, useEffect } from "react";

export function ScrollThread() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function onScroll() {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(total > 0 ? window.scrollY / total : 0);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="fixed left-0 top-0 z-50 h-full w-[2px] bg-brand-mist">
      <div
        className="w-full bg-brand-goldenrod transition-all duration-micro"
        style={{ height: `${progress * 100}%` }}
      />
    </div>
  );
}

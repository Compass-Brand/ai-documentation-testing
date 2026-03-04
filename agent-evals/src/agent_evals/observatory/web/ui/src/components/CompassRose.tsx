export function CompassRose() {
  return (
    <div
      className="pointer-events-none select-none"
      style={{ opacity: 0.08 }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 200 200"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-48 h-48 mx-auto animate-[spin_120s_linear_infinite]"
      >
        {/* North arrow */}
        <polygon points="100,10 110,90 90,90" fill="#C2A676" />
        {/* South arrow */}
        <polygon points="100,190 110,110 90,110" fill="#C2A676" />
        {/* East arrow */}
        <polygon points="190,100 110,110 110,90" fill="#C2A676" />
        {/* West arrow */}
        <polygon points="10,100 90,110 90,90" fill="#C2A676" />
        {/* NE */}
        <polygon points="163,37 115,95 105,85" fill="#C2A676" opacity="0.6" />
        {/* NW */}
        <polygon points="37,37 85,85 95,95" fill="#C2A676" opacity="0.6" />
        {/* SE */}
        <polygon
          points="163,163 115,105 105,115"
          fill="#C2A676"
          opacity="0.6"
        />
        {/* SW */}
        <polygon points="37,163 85,115 95,105" fill="#C2A676" opacity="0.6" />
        {/* Center circle */}
        <circle cx="100" cy="100" r="8" fill="#C2A676" />
        <circle cx="100" cy="100" r="5" fill="white" />
        {/* Outer ring */}
        <circle cx="100" cy="100" r="85" stroke="#C2A676" strokeWidth="1" />
        <circle cx="100" cy="100" r="80" stroke="#C2A676" strokeWidth="0.5" />
      </svg>
    </div>
  );
}

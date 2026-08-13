/**
 * The brand mark: a radar sweeping for hackathons.
 *
 * Matches favicon.svg — one bold ring plus a rotating arm, because
 * anything busier stops reading at small sizes. Pure SVG + CSS so it
 * scales anywhere and costs nothing to animate; the sweep and blips stop
 * under prefers-reduced-motion.
 */
export default function RadarMark({ size = 34, className = '' }) {
  return (
    <div className={`radar-mark ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
        <defs>
          <linearGradient id="radar-bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#4f46e5" />
            <stop offset="1" stopColor="#a855f7" />
          </linearGradient>
          <clipPath id="radar-clip">
            <circle cx="50" cy="50" r="34" />
          </clipPath>
        </defs>

        <rect width="100" height="100" rx="22" fill="url(#radar-bg)" />

        {/* range ring */}
        <circle
          className="radar-ring"
          cx="50"
          cy="50"
          r="30"
          fill="none"
          stroke="#fff"
          strokeWidth="7.4"
        />

        {/* the arm and its trailing wedge rotate together */}
        <g className="radar-sweep">
          <g clipPath="url(#radar-clip)">
            <path d="M50 50 L50 16 A34 34 0 0 1 79 33 Z" fill="rgba(255,255,255,0.28)" />
          </g>
          <line
            x1="50"
            y1="50"
            x2="74"
            y2="26"
            stroke="#fff"
            strokeWidth="7.4"
            strokeLinecap="round"
          />
        </g>

        {/* contacts, lighting up as the arm passes over them */}
        <circle className="radar-blip b1" cx="74" cy="26" r="10" fill="#fff" />
        <circle className="radar-blip b2" cx="30" cy="64" r="6" fill="#fff" />
      </svg>
    </div>
  )
}

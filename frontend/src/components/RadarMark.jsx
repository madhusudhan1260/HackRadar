/**
 * The brand mark: a radar sweeping for hackathons.
 *
 * Matches favicon.svg. Built from filled area rather than thin strokes —
 * hairlines vanish when a browser downsamples an icon to 16px, whereas a
 * solid wedge keeps its silhouette. The wedge rotates; contacts flash as
 * it crosses them. Both stop under prefers-reduced-motion.
 */
export default function RadarMark({ size = 34, className = '' }) {
  return (
    <div className={`radar-mark ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
        <defs>
          <linearGradient id="radar-plate" x1="0" y1="0" x2="0.3" y2="1">
            <stop offset="0" stopColor="#5850ec" />
            <stop offset="1" stopColor="#a855f7" />
          </linearGradient>
          {/* Light along the top edge, so the mark reads as an object. */}
          <radialGradient id="radar-gloss" cx="0.5" cy="0" r="0.9">
            <stop offset="0" stopColor="#fff" stopOpacity="0.28" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect width="100" height="100" rx="23" fill="url(#radar-plate)" />
        <rect width="100" height="100" rx="23" fill="url(#radar-gloss)" />

        <circle cx="50" cy="50" r="31" fill="none" stroke="#fff" strokeWidth="8" />

        <g className="radar-sweep">
          <path d="M50 50 L50 19 A31 31 0 0 1 76.8 34.5 Z" fill="#fff" />
        </g>

        <circle cx="50" cy="50" r="5.5" fill="#fff" />

        {/* contacts, lighting up as the wedge passes over them */}
        <circle className="radar-blip b1" cx="66" cy="34" r="4.5" fill="#fff" />
        <circle className="radar-blip b2" cx="35" cy="63" r="3.5" fill="#fff" />
      </svg>
    </div>
  )
}

/**
 * The brand mark: a radar dish sweeping for hackathons.
 *
 * Pure SVG + CSS so it scales anywhere and costs nothing to animate.
 * The sweep, rings and blips all stop under prefers-reduced-motion.
 */
export default function RadarMark({ size = 34, className = '' }) {
  return (
    <div className={`radar-mark ${className}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
        <defs>
          <radialGradient id="radar-sweep-grad">
            <stop offset="0%" stopColor="rgba(255,255,255,0.9)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <clipPath id="radar-clip">
            <circle cx="50" cy="50" r="46" />
          </clipPath>
        </defs>

        {/* concentric range rings */}
        <circle className="radar-ring" cx="50" cy="50" r="46" />
        <circle className="radar-ring" cx="50" cy="50" r="31" />
        <circle className="radar-ring" cx="50" cy="50" r="16" />

        {/* cross hairs */}
        <line className="radar-ring" x1="50" y1="4" x2="50" y2="96" />
        <line className="radar-ring" x1="4" y1="50" x2="96" y2="50" />

        {/* rotating sweep wedge */}
        <g clipPath="url(#radar-clip)">
          <path
            className="radar-sweep"
            d="M50 50 L50 2 A48 48 0 0 1 92 32 Z"
            fill="url(#radar-sweep-grad)"
          />
        </g>

        {/* contacts that blink as the sweep passes */}
        <circle className="radar-blip b1" cx="68" cy="34" r="3.4" />
        <circle className="radar-blip b2" cx="33" cy="63" r="2.8" />
        <circle className="radar-blip b3" cx="62" cy="70" r="2.4" />
      </svg>
    </div>
  )
}

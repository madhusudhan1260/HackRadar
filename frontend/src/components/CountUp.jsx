import { useEffect, useRef, useState } from 'react'

/**
 * Counts from 0 up to `value` when it first appears.
 *
 * Uses an eased rAF loop rather than a timer so it stays smooth, and jumps
 * straight to the final number for reduced-motion users.
 */
export default function CountUp({ value = 0, duration = 1100, className = '' }) {
  const [display, setDisplay] = useState(0)
  const frame = useRef(0)

  useEffect(() => {
    const target = Number(value) || 0

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(target)
      return undefined
    }

    let start = 0
    const step = (time) => {
      if (!start) start = time
      const progress = Math.min((time - start) / duration, 1)
      // easeOutExpo — fast off the line, gentle landing.
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
      setDisplay(Math.round(target * eased))
      if (progress < 1) frame.current = requestAnimationFrame(step)
    }

    frame.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame.current)
  }, [value, duration])

  return <span className={className}>{display.toLocaleString()}</span>
}

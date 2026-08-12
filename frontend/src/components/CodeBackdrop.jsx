import { useEffect, useRef } from 'react'

/**
 * Canvas "code rain" behind the login screen.
 *
 * Drawn on canvas rather than with DOM nodes so hundreds of glyphs cost one
 * paint instead of hundreds of layout nodes. It throttles to ~24fps, pauses
 * entirely when the tab is hidden, and does not run at all for visitors who
 * asked for reduced motion.
 */

const GLYPHS = '01{}[]()<>/*+-=;:$#@!&|?abcdefghijklmnopqrstuvwxyz01'
const FONT_SIZE = 14
const FRAME_MS = 1000 / 24

export default function CodeBackdrop() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) return undefined

    const canvas = canvasRef.current
    if (!canvas) return undefined
    const context = canvas.getContext('2d', { alpha: true })

    let columns = []
    let width = 0
    let height = 0
    let frame = 0
    let last = 0
    let running = true

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = width * ratio
      canvas.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.font = `${FONT_SIZE}px ui-monospace, SFMono-Regular, Menlo, monospace`

      const count = Math.ceil(width / FONT_SIZE)
      columns = Array.from({ length: count }, () => ({
        // Stagger the start so the rain doesn't fall as one solid wall.
        y: Math.random() * -height,
        speed: 0.4 + Math.random() * 0.9,
        bright: Math.random() < 0.22,
      }))
    }

    const draw = (time) => {
      if (!running) return
      frame = requestAnimationFrame(draw)
      if (time - last < FRAME_MS) return
      last = time

      // Translucent wash instead of clearRect leaves the fading trail.
      context.fillStyle = 'rgba(10, 14, 23, 0.09)'
      context.fillRect(0, 0, width, height)

      columns.forEach((column, index) => {
        const x = index * FONT_SIZE
        const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)]

        context.fillStyle = column.bright
          ? 'rgba(165, 180, 252, 0.85)'
          : 'rgba(99, 102, 241, 0.34)'
        context.fillText(glyph, x, column.y)

        column.y += column.speed * FONT_SIZE * 0.55
        if (column.y > height + FONT_SIZE) {
          column.y = -FONT_SIZE * (2 + Math.random() * 12)
          column.speed = 0.4 + Math.random() * 0.9
          column.bright = Math.random() < 0.22
        }
      })
    }

    const onVisibility = () => {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(frame)
      } else if (!running) {
        running = true
        last = 0
        frame = requestAnimationFrame(draw)
      }
    }

    resize()
    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', onVisibility)
    frame = requestAnimationFrame(draw)

    return () => {
      running = false
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <canvas ref={canvasRef} className="code-rain" aria-hidden="true" />
}

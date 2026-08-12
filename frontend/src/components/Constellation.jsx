import { useEffect, useRef } from 'react'

/**
 * Drifting node network behind the login screen — the "radar mesh".
 *
 * Nodes wander slowly and draw a line to any neighbour within range, with
 * the line fading as the gap widens. Neighbour search is O(n²), which is
 * fine at this node count and avoids a spatial index for decoration.
 */

const MAX_NODES = 46
const LINK_DISTANCE = 148
const FRAME_MS = 1000 / 30

export default function Constellation() {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined

    const canvas = canvasRef.current
    if (!canvas) return undefined
    const context = canvas.getContext('2d')

    let nodes = []
    let width = 0
    let height = 0
    let frame = 0
    let last = 0
    let running = true
    const pointer = { x: -999, y: -999 }

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = width * ratio
      canvas.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)

      // Fewer nodes on small screens — same look, less work.
      const count = Math.min(MAX_NODES, Math.round((width * height) / 26000))
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 1 + Math.random() * 1.8,
      }))
    }

    const draw = (time) => {
      if (!running) return
      frame = requestAnimationFrame(draw)
      if (time - last < FRAME_MS) return
      last = time

      context.clearRect(0, 0, width, height)

      nodes.forEach((node) => {
        node.x += node.vx
        node.y += node.vy
        if (node.x < 0 || node.x > width) node.vx *= -1
        if (node.y < 0 || node.y > height) node.vy *= -1
      })

      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i]

        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const distance = Math.hypot(dx, dy)
          if (distance > LINK_DISTANCE) continue

          context.strokeStyle = `rgba(129, 140, 248, ${0.2 * (1 - distance / LINK_DISTANCE)})`
          context.lineWidth = 1
          context.beginPath()
          context.moveTo(a.x, a.y)
          context.lineTo(b.x, b.y)
          context.stroke()
        }

        // Nodes near the cursor light up, so the mesh feels alive.
        const near = Math.hypot(a.x - pointer.x, a.y - pointer.y) < 130
        context.fillStyle = near ? 'rgba(196, 181, 253, 0.9)' : 'rgba(129, 140, 248, 0.42)'
        context.beginPath()
        context.arc(a.x, a.y, near ? a.r * 1.7 : a.r, 0, Math.PI * 2)
        context.fill()
      }
    }

    const onPointer = (event) => {
      pointer.x = event.clientX
      pointer.y = event.clientY
    }
    const onLeave = () => {
      pointer.x = -999
      pointer.y = -999
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
    window.addEventListener('pointermove', onPointer)
    window.addEventListener('pointerleave', onLeave)
    document.addEventListener('visibilitychange', onVisibility)
    frame = requestAnimationFrame(draw)

    return () => {
      running = false
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('pointerleave', onLeave)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <canvas ref={canvasRef} className="constellation" aria-hidden="true" />
}

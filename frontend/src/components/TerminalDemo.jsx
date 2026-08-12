import { useEffect, useRef, useState } from 'react'

/**
 * A fake HackRadar terminal session that types itself out on the login
 * screen. Purely decorative — it shows what the product does while the
 * visitor signs in.
 */

const SCRIPT = [
  { text: '$ hackradar ingest --all', kind: 'cmd' },
  { text: '→ devpost   fetched 60   new 12', kind: 'out' },
  { text: '→ mlh       fetched 80   new 7', kind: 'out' },
  { text: '✓ classified 164 hackathons', kind: 'ok' },
  { text: '', kind: 'gap' },
  { text: '$ hackradar match --profile me', kind: 'cmd' },
  { text: '  73%  IIT Bombay ML Challenge', kind: 'hi' },
  { text: '  67%  Arm AI Optimization', kind: 'hi' },
  { text: '  11%  ETHIndia  ⚠ requires Solidity', kind: 'warn' },
  { text: '', kind: 'gap' },
  { text: '$ hackradar deadlines --today', kind: 'cmd' },
  { text: '! 3 closing in 24h — alert sent', kind: 'alert' },
]

const TYPE_MS = 26
const LINE_PAUSE_MS = 520
const RESTART_MS = 3200

export default function TerminalDemo() {
  const [lines, setLines] = useState([])
  const [typing, setTyping] = useState('')
  const timers = useRef([])

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      setLines(SCRIPT)
      return undefined
    }

    let cancelled = false
    const wait = (ms) =>
      new Promise((resolve) => {
        const id = setTimeout(resolve, ms)
        timers.current.push(id)
      })

    const run = async () => {
      while (!cancelled) {
        setLines([])
        setTyping('')

        for (const line of SCRIPT) {
          if (cancelled) return

          if (line.kind === 'gap') {
            setLines((current) => [...current, line])
            await wait(200)
            continue
          }

          // Commands type character by character; output appears at once,
          // which is how a real terminal behaves.
          if (line.kind === 'cmd') {
            for (let i = 1; i <= line.text.length; i += 1) {
              if (cancelled) return
              setTyping(line.text.slice(0, i))
              await wait(TYPE_MS)
            }
            setTyping('')
          }

          setLines((current) => [...current, line])
          await wait(line.kind === 'cmd' ? 260 : LINE_PAUSE_MS)
        }

        await wait(RESTART_MS)
      }
    }

    run()
    return () => {
      cancelled = true
      timers.current.forEach(clearTimeout)
      timers.current = []
    }
  }, [])

  return (
    <div className="terminal" aria-hidden="true">
      <div className="terminal-bar">
        <span className="dot red" />
        <span className="dot amber" />
        <span className="dot green" />
        <span className="terminal-title">hackradar — zsh</span>
      </div>
      <div className="terminal-body">
        {lines.map((line, index) => (
          <div key={`${line.text}-${index}`} className={`t-line ${line.kind}`}>
            {line.text || ' '}
          </div>
        ))}
        {typing && (
          <div className="t-line cmd">
            {typing}
            <span className="caret" />
          </div>
        )}
      </div>
    </div>
  )
}

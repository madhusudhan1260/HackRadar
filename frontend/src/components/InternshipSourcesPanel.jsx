import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Internship-collector equivalent of SourcesPanel — split out rather than
 * folded into it because the two hit entirely different endpoints
 * (/internships/sources, /internships/ingest) with no shared state, same
 * reasoning as internship_collectors staying a separate hierarchy on the
 * backend rather than bending the hackathons one to fit.
 */
export default function InternshipSourcesPanel({ onIngested, toast }) {
  const [sources, setSources] = useState(null)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState('')
  const [error, setError] = useState(null)

  const load = () => {
    api.internshipSources().then(setSources).catch((err) => setError(err.message))
  }

  useEffect(load, [])

  const runIngest = async (name) => {
    setBusy(true)
    setLog(`Collecting from ${name || 'all enabled sources'}…`)
    try {
      const results = await api.internshipIngest(name ? [name] : null)
      setLog(
        results
          .map((r) =>
            r.ok
              ? `${r.source}: ${r.fetched} fetched, ${r.created} new, ${r.updated} updated`
              : `${r.source}: FAILED — ${r.error}`,
          )
          .join('\n'),
      )
      const added = results.reduce((n, r) => n + (r.created || 0), 0)
      const failed = results.filter((r) => !r.ok)
      if (failed.length) toast?.error(`${failed.map((r) => r.source).join(', ')} failed`)
      else toast?.success(added ? `${added} new internship(s) added` : 'Already up to date')
      load()
      onIngested?.()
    } catch (err) {
      toast?.error(err.message)
      setLog(`Failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="error-banner">{error}</div>
  if (!sources) return <div className="empty">Loading internship sources…</div>

  return (
    <div className="panel">
      <h2>💼 Internship sources</h2>
      <p className="hint">
        Same idea as hackathon sources, separate pipeline. Real collectors only — anything
        disabled stays that way until it has a legitimate way in (see its note below).
      </p>

      {sources.map((source) => (
        <div key={source.name} className="source-row">
          <span
            className={`dot ${
              !source.enabled ? 'off' : source.last_ok === false ? 'err' : 'on'
            }`}
          />
          <div className="info">
            <div className="name">
              {source.name}{' '}
              <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>
                · {source.count} listing{source.count === 1 ? '' : 's'}
              </span>
            </div>
            <div className="note">
              {source.enabled ? source.access_note : `Disabled — ${source.access_note}`}
            </div>
          </div>
          <button
            className="btn"
            disabled={busy || !source.enabled}
            onClick={() => runIngest(source.name)}
          >
            Run
          </button>
        </div>
      ))}

      <button
        className="btn primary"
        style={{ marginTop: 12 }}
        disabled={busy}
        onClick={() => runIngest(null)}
      >
        {busy ? 'Collecting…' : '↻ Refresh all internship sources'}
      </button>

      {log && (
        <pre
          style={{
            marginTop: 14,
            padding: 12,
            background: 'var(--bg-elev-2)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--text-dim)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {log}
        </pre>
      )}
    </div>
  )
}

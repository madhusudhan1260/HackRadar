import { useEffect, useState } from 'react'
import { api } from '../api'

export default function SourcesPanel({ onIngested, toast }) {
  const [sources, setSources] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [busy, setBusy] = useState(false)
  const [sendingNotifs, setSendingNotifs] = useState(false)
  const [log, setLog] = useState('')
  const [error, setError] = useState(null)

  const load = () => {
    api.sources().then(setSources).catch((err) => setError(err.message))
    api.notificationPreview().then(setAlerts).catch(() => {})
  }

  useEffect(load, [])

  const sendNow = async () => {
    setSendingNotifs(true)
    try {
      const result = await api.sendNotifications()
      if (result.sent > 0) {
        toast?.success(
          `Sent ${result.sent} alert${result.sent === 1 ? '' : 's'} via ${result.channels.join(', ')}.`,
        )
      } else if (result.note) {
        toast?.error(result.note)
      } else {
        toast?.info('Nothing due to send right now.')
      }
      load()
    } catch (err) {
      toast?.error(err.message)
    } finally {
      setSendingNotifs(false)
    }
  }

  const runIngest = async (name) => {
    setBusy(true)
    setLog(`Collecting from ${name || 'all enabled sources'}…`)
    try {
      const results = await api.ingest(name ? [name] : null)
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
      else toast?.success(added ? `${added} new hackathon(s) added` : 'Already up to date')
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
  if (!sources) return <div className="empty">Loading sources…</div>

  return (
    <>
      <div className="panel">
        <h2>🔌 Data sources</h2>
        <p className="hint">
          Collectors run automatically on a schedule. You can also trigger one by hand.
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
          {busy ? 'Collecting…' : '↻ Refresh all sources'}
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

      <div className="panel">
        <h2>🔔 Notifications</h2>
        <p className="hint">
          Alerts fire at 7, 3 and 1 day before a deadline for anything you saved or that
          scores above your threshold.
        </p>

        {!alerts && <p className="muted">Loading…</p>}

        {alerts && (
          <>
            <div className="meta-row" style={{ marginBottom: 12 }}>
              <span>{alerts.email_configured ? '✅' : '⚪'} Email</span>
              <span>{alerts.telegram_configured ? '✅' : '⚪'} Telegram</span>
              <span>{alerts.count} alert{alerts.count === 1 ? '' : 's'} queued</span>
              {alerts.count > 0 && (
                <button
                  className="btn primary"
                  style={{ marginLeft: 'auto' }}
                  disabled={sendingNotifs}
                  onClick={sendNow}
                >
                  {sendingNotifs ? 'Sending…' : '📧 Send now'}
                </button>
              )}
            </div>
            {alerts.count > 0 && (
              <p className="assist-note" style={{ marginBottom: 12 }}>
                These also send automatically in the background — this button
                is for testing delivery right now instead of waiting.
              </p>
            )}

            {alerts.email_configured && (
              <p className="assist-note" style={{ marginBottom: 12 }}>
                Sent to your account email automatically — no setup needed.
              </p>
            )}

            {!alerts.email_configured && !alerts.telegram_configured && (
              <p className="warn-note">
                No delivery channel reachable right now — alerts still show up
                here in the meantime. If this persists, the admin needs to
                check the email provider configuration.
              </p>
            )}

            {alerts.alerts.map((alert) => (
              <div key={`${alert.id}-${alert.days_left}`} className="board-row">
                <span className="name">{alert.title}</span>
                <span className="when">
                  {alert.days_left === 0 ? 'today' : `in ${alert.days_left}d`} ·{' '}
                  {alert.match_score}%
                </span>
              </div>
            ))}

            {alerts.count === 0 && (
              <p className="muted">Nothing queued right now.</p>
            )}
          </>
        )}
      </div>
    </>
  )
}

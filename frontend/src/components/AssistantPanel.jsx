import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * The AI column beside the hackathon list.
 *
 * Shows how ready the profile is, and drafts the answers a chosen
 * hackathon's application will ask for, so they can be copied straight
 * across. The browser extension does the actual filling on the external
 * site; this is the in-app companion to it.
 */

const QUESTIONS = [
  { kind: 'motivation', label: 'Why do you want to participate?' },
  { kind: 'pitch', label: 'Why should we select you?' },
  { kind: 'goals', label: 'What do you hope to learn?' },
  { kind: 'project', label: 'Your project idea' },
]

const FIELD_LABELS = {
  full_name: 'Name', email: 'Email', phone: 'Phone', college: 'College',
  degree: 'Degree', branch: 'Branch', year_of_study: 'Year',
  graduation_year: 'Graduation year', registration_number: 'Roll number',
  city: 'City', github_url: 'GitHub', linkedin_url: 'LinkedIn',
  portfolio_url: 'Portfolio', resume_url: 'Resume', skills: 'Skills',
  bio: 'Bio', experience: 'Experience', achievements: 'Achievements',
}

export default function AssistantPanel({ hackathons = [], toast }) {
  const [readiness, setReadiness] = useState(null)
  const [targetId, setTargetId] = useState('')
  const [answers, setAnswers] = useState({})
  const [busyKind, setBusyKind] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    api.formReadiness().then(setReadiness).catch(() => {})
  }, [])

  // Default to whatever is top of the list — usually the most urgent.
  useEffect(() => {
    if (!targetId && hackathons.length) setTargetId(String(hackathons[0].id))
  }, [hackathons, targetId])

  const target = hackathons.find((h) => String(h.id) === String(targetId))

  const write = async (kind, label) => {
    setBusyKind(kind)
    try {
      const result = await api.generateAnswer({
        question: label,
        kind,
        hackathon_id: target ? target.id : null,
        page_title: target ? target.title : '',
      })
      setAnswers((current) => ({ ...current, [kind]: result }))
    } catch (error) {
      toast?.error(error.message)
    } finally {
      setBusyKind('')
    }
  }

  const copy = async (kind, text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(kind)
      setTimeout(() => setCopied(''), 1800)
    } catch {
      toast?.error('Clipboard blocked by the browser.')
    }
  }

  return (
    <aside className="assistant">
      <div className="assistant-head">
        <h2>✨ Application AI</h2>
        <p>Draft the answers an application will ask for.</p>
      </div>

      {/* --- profile readiness --- */}
      {readiness && (
        <section className="assist-card">
          <div className="ready-top">
            <strong>Profile</strong>
            <span className={`ready-pct ${readiness.percent >= 80 ? 'good' : readiness.percent >= 50 ? 'ok' : 'low'}`}>
              {readiness.percent}%
            </span>
          </div>
          <div className="ready-bar">
            <div style={{ width: `${readiness.percent}%` }} />
          </div>
          {readiness.missing.length > 0 ? (
            <p className="assist-note">
              Missing{' '}
              {readiness.missing
                .slice(0, 4)
                .map((k) => FIELD_LABELS[k] || k)
                .join(', ')}
              {readiness.missing.length > 4 && ` +${readiness.missing.length - 4} more`}.
            </p>
          ) : (
            <p className="assist-note">Everything an application asks for is filled in.</p>
          )}
        </section>
      )}

      {/* --- pick a hackathon --- */}
      <section className="assist-card">
        <label className="assist-label" htmlFor="assist-target">
          Prepare for
        </label>
        <select
          id="assist-target"
          value={targetId}
          onChange={(event) => {
            setTargetId(event.target.value)
            setAnswers({})
          }}
        >
          {hackathons.length === 0 && <option value="">No hackathons in view</option>}
          {hackathons.map((h) => (
            <option key={h.id} value={h.id}>
              {h.title.slice(0, 52)}
            </option>
          ))}
        </select>
        {target && (
          <p className="assist-note">
            Answers are written from your skills and this event's theme
            {target.match ? ` · ${target.match.score}% match` : ''}.
          </p>
        )}
      </section>

      {/* --- draft answers --- */}
      {QUESTIONS.map(({ kind, label }) => {
        const answer = answers[kind]
        return (
          <section className="assist-card" key={kind}>
            <div className="assist-q">{label}</div>

            {!answer && (
              <button
                className="btn"
                disabled={!target || busyKind === kind}
                onClick={() => write(kind, label)}
              >
                {busyKind === kind ? 'Writing…' : '✨ Draft answer'}
              </button>
            )}

            {answer && (
              <>
                <textarea
                  className="assist-answer"
                  rows={6}
                  value={answer.answer}
                  onChange={(event) =>
                    setAnswers((c) => ({ ...c, [kind]: { ...answer, answer: event.target.value } }))
                  }
                />
                <div className="assist-actions">
                  <span className={`src ${answer.source}`}>
                    {answer.source === 'claude' ? 'Written by Claude' : 'Template draft'}
                  </span>
                  <button className="link-btn" onClick={() => write(kind, label)}>
                    Rewrite
                  </button>
                  <button className="link-btn" onClick={() => copy(kind, answer.answer)}>
                    {copied === kind ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </>
            )}
          </section>
        )
      })}

      <section className="assist-card extension-cta">
        <strong>🧩 Fill forms automatically</strong>
        <p className="assist-note">
          The browser extension fills these answers straight into a hackathon's
          own registration form. It never submits — you review and press submit
          yourself.
        </p>
        <a
          className="link-btn"
          href="https://github.com/madhusudhan1260/HackRadar/tree/main/extension"
          target="_blank"
          rel="noreferrer"
        >
          Install instructions ↗
        </a>
      </section>
    </aside>
  )
}

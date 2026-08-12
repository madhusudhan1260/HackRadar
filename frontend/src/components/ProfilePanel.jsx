import { useEffect, useState } from 'react'
import { api } from '../api'
import { CATEGORY_LABELS } from '../format'

const SKILL_SUGGESTIONS = [
  'Python', 'C++', 'Java', 'JavaScript', 'TypeScript', 'React', 'HTML/CSS',
  'SQL', 'Machine Learning', 'Deep Learning', 'LLM', 'NLP', 'Computer Vision',
  'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Android', 'Flutter', 'iOS',
  'Cybersecurity', 'Blockchain', 'Solidity', 'IoT', 'UI/UX', 'Go', 'Rust',
]

export default function ProfilePanel({ onSaved }) {
  const [profile, setProfile] = useState(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    api.profile().then(setProfile).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="error-banner">{error}</div>
  if (!profile) return <div className="empty">Loading profile…</div>

  const set = (patch) => setProfile({ ...profile, ...patch })

  const toggleSkill = (skill) => {
    const has = profile.skills.includes(skill)
    set({ skills: has ? profile.skills.filter((s) => s !== skill) : [...profile.skills, skill] })
  }

  const toggleInterest = (key) => {
    const has = profile.interests.includes(key)
    set({
      interests: has ? profile.interests.filter((i) => i !== key) : [...profile.interests, key],
    })
  }

  const save = async () => {
    setStatus('Saving…')
    try {
      await api.saveProfile({
        name: profile.name,
        email: profile.email,
        skills: profile.skills,
        interests: profile.interests,
        prefer_mode: profile.prefer_mode,
        india_only: profile.india_only,
        min_prize_inr: Number(profile.min_prize_inr) || 0,
        free_only: profile.free_only,
        team_size: Number(profile.team_size) || 1,
        notify_min_score: Number(profile.notify_min_score) || 0,
        telegram_chat_id: profile.telegram_chat_id,
      })
      setStatus('Saved — match scores updated')
      onSaved?.()
      setTimeout(() => setStatus(''), 2500)
    } catch (err) {
      setStatus(`Failed: ${err.message}`)
    }
  }

  return (
    <div className="panel">
      <h2>🧠 My profile</h2>
      <p className="hint">
        Match scores are calculated from this. The more accurate it is, the better the
        recommendations.
      </p>

      <div className="inline-fields">
        <div className="field">
          <label>Name</label>
          <input
            type="text"
            value={profile.name}
            onChange={(event) => set({ name: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Email (for deadline alerts)</label>
          <input
            type="email"
            value={profile.email}
            placeholder="you@example.com"
            onChange={(event) => set({ email: event.target.value })}
          />
        </div>
      </div>

      <div className="field">
        <label>My skills ({profile.skills.length} selected)</label>
        <div className="chips">
          {[...new Set([...SKILL_SUGGESTIONS, ...profile.skills])].map((skill) => (
            <button
              key={skill}
              className={`chip ${profile.skills.includes(skill) ? 'on' : ''}`}
              onClick={() => toggleSkill(skill)}
            >
              {profile.skills.includes(skill) ? '✓ ' : ''}
              {skill}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Interests</label>
        <div className="chips">
          {Object.entries(CATEGORY_LABELS)
            .filter(([key]) => key !== 'general')
            .map(([key, label]) => (
              <button
                key={key}
                className={`chip ${profile.interests.includes(key) ? 'on' : ''}`}
                onClick={() => toggleInterest(key)}
              >
                {label}
              </button>
            ))}
        </div>
      </div>

      <div className="inline-fields">
        <div className="field">
          <label>Preferred mode</label>
          <select
            value={profile.prefer_mode}
            onChange={(event) => set({ prefer_mode: event.target.value })}
          >
            <option value="any">Any</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </div>
        <div className="field">
          <label>Team size</label>
          <input
            type="number"
            min="1"
            max="20"
            value={profile.team_size}
            onChange={(event) => set({ team_size: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Minimum prize (₹)</label>
          <input
            type="number"
            min="0"
            step="1000"
            value={profile.min_prize_inr}
            onChange={(event) => set({ min_prize_inr: event.target.value })}
          />
        </div>
        <div className="field">
          <label>Alert me above match %</label>
          <input
            type="number"
            min="0"
            max="100"
            value={profile.notify_min_score}
            onChange={(event) => set({ notify_min_score: event.target.value })}
          />
        </div>
      </div>

      <button className="btn primary" onClick={save}>
        Save profile
      </button>
      {status && (
        <span style={{ marginLeft: 12, color: 'var(--text-dim)', fontSize: 13 }}>{status}</span>
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import CodeBackdrop from '../components/CodeBackdrop'
import Constellation from '../components/Constellation'
import CountUp from '../components/CountUp'
import RadarMark from '../components/RadarMark'
import TerminalDemo from '../components/TerminalDemo'

/**
 * Sign-in screen.
 *
 * Two doors: `portal = 'user'` for everyone, `portal = 'admin'` for staff.
 * The admin door sends as_admin=true, and the API refuses any account
 * without the admin role — so it is a real boundary, not a UI hint.
 *
 * Modes within the user door:
 *   signin  — username + password (no OTP; the everyday path)
 *   signup  — details, then a one-time OTP to verify the phone
 *   otp     — enter the code (registration or password reset)
 *   forgot  — request a reset code, then set a new password
 */

const FLOAT_TOKENS = [
  'def train():', '</>', 'git push', 'async/await', '{ }', 'npm run dev',
  'SELECT *', '→ 200 OK', 'pip install', 'const [x] =', '#!/bin/bash',
  'docker up', 'O(n log n)', 'return 0;', '=> match()',
]

export default function Login() {
  const { signIn } = useAuth()
  const [portal, setPortal] = useState('user')
  const [mode, setMode] = useState('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [form, setForm] = useState({
    name: '', username: '', phone: '', password: '', code: '', newPassword: '',
  })

  const [otp, setOtp] = useState(null)
  const [otpPurpose, setOtpPurpose] = useState('register')
  const [resendIn, setResendIn] = useState(0)
  const [usernameHint, setUsernameHint] = useState(null)
  const usernameTimer = useRef(null)
  const cardRef = useRef(null)

  const set = (patch) => setForm((current) => ({ ...current, ...patch }))

  useEffect(() => {
    if (resendIn <= 0) return undefined
    const timer = setTimeout(() => setResendIn((value) => value - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  // Subtle parallax: the card leans towards the pointer.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined
    const card = cardRef.current
    if (!card) return undefined

    const onMove = (event) => {
      const box = card.getBoundingClientRect()
      const dx = (event.clientX - (box.left + box.width / 2)) / box.width
      const dy = (event.clientY - (box.top + box.height / 2)) / box.height
      // Clamped so it never becomes a distracting swing.
      const clamp = (v) => Math.max(-1, Math.min(1, v))
      card.style.setProperty('--tilt-x', `${clamp(dy) * -4}deg`)
      card.style.setProperty('--tilt-y', `${clamp(dx) * 5}deg`)
    }
    const onLeave = () => {
      card.style.setProperty('--tilt-x', '0deg')
      card.style.setProperty('--tilt-y', '0deg')
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerleave', onLeave)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  const goTo = (nextMode) => {
    setMode(nextMode)
    setError('')
    setNotice('')
  }

  const switchPortal = (next) => {
    setPortal(next)
    setMode('signin')
    setError('')
    setNotice('')
    setUsernameHint(null)
  }

  const run = async (action) => {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const onUsernameChange = (value) => {
    set({ username: value })
    setUsernameHint(null)
    clearTimeout(usernameTimer.current)
    if (mode !== 'signup' || value.trim().length < 3) return
    usernameTimer.current = setTimeout(() => {
      api.checkUsername(value).then(setUsernameHint).catch(() => setUsernameHint(null))
    }, 400)
  }

  const startOtp = (result, purpose) => {
    setOtp(result)
    setOtpPurpose(purpose)
    setResendIn(result.resend_in || 60)
    setMode('otp')
    setNotice(`We sent a 6-digit code to ${result.phone_masked}.`)
  }

  // --- actions ---------------------------------------------------------

  const doSignIn = () =>
    run(async () => {
      const result = await api.login(form.username, form.password, portal === 'admin')
      signIn(result.token, result.user)
    })

  const doSignUp = () =>
    run(async () => {
      const result = await api.register({
        name: form.name,
        username: form.username,
        phone: form.phone,
        password: form.password,
      })
      startOtp(result, 'register')
    })

  const doVerify = () =>
    run(async () => {
      const result =
        otpPurpose === 'register'
          ? await api.verifyOtp(form.username, form.code)
          : await api.resetPassword(form.username, form.code, form.newPassword)
      signIn(result.token, result.user)
    })

  const doResend = () =>
    run(async () => {
      const result =
        otpPurpose === 'register'
          ? await api.resendOtp(form.username)
          : await api.forgotPassword(form.username)
      startOtp(result, otpPurpose)
      setNotice(`New code sent to ${result.phone_masked}.`)
    })

  const doForgot = () =>
    run(async () => {
      const result = await api.forgotPassword(form.username)
      startOtp(result, 'reset')
      setNotice(`Reset code sent to ${result.phone_masked}. Enter it with your new password.`)
    })

  const submit = (event) => {
    event.preventDefault()
    if (busy) return
    if (mode === 'signin') doSignIn()
    else if (mode === 'signup') doSignUp()
    else if (mode === 'otp') doVerify()
    else if (mode === 'forgot') doForgot()
  }

  const isAdmin = portal === 'admin'

  const submitLabel = busy
    ? 'Please wait…'
    : mode === 'signin'
      ? isAdmin ? 'Enter admin portal' : 'Sign in'
      : mode === 'signup'
        ? 'Send verification code'
        : mode === 'otp'
          ? otpPurpose === 'reset' ? 'Reset password' : 'Verify and continue'
          : 'Send reset code'

  return (
    <div className={`auth-shell ${isAdmin ? 'admin-mode' : ''}`}>
      <CodeBackdrop />
      <Constellation />
      <div className="scanline" aria-hidden="true" />
      <div className="aurora" aria-hidden="true">
        <span className="orb orb-1" />
        <span className="orb orb-2" />
        <span className="orb orb-3" />
      </div>
      <div className="float-layer" aria-hidden="true">
        {FLOAT_TOKENS.map((token, index) => (
          <span key={token} className={`float-token f${index % 5}`} style={{ '--i': index }}>
            {token}
          </span>
        ))}
      </div>

      <div className="auth-layout">
        {/* ---------------- showcase ---------------- */}
        <section className="auth-showcase">
          <div className="brand">
            <RadarMark size={38} />
            <h1>HackRadar</h1>
          </div>
          <h2 className="showcase-head">
            Never miss a<br />
            <span className="grad">hackathon</span> again.
          </h2>
          <p className="showcase-sub">
            Devpost, MLH and more — collected, de-duplicated, ranked against your
            skills, and watched for deadlines. One dashboard instead of ten tabs.
          </p>

          <TerminalDemo />

          <div className="showcase-stats">
            <div>
              <strong><CountUp value={164} /></strong>
              <span>hackathons tracked</span>
            </div>
            <div>
              <strong><CountUp value={3} duration={800} /></strong>
              <span>sources merged</span>
            </div>
            <div>
              <strong><CountUp value={15} duration={950} /></strong>
              <span>categories classified</span>
            </div>
          </div>

          <div className="stack-row">
            {['Python', 'FastAPI', 'React', 'SQLAlchemy', 'Vite'].map((tech, index) => (
              <span key={tech} className="stack-chip" style={{ '--d': index }}>
                {tech}
              </span>
            ))}
          </div>
        </section>

        {/* ---------------- auth card ---------------- */}
        <section className="auth-card" ref={cardRef}>
          <div className="portal-switch" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={!isAdmin}
              className={!isAdmin ? 'on' : ''}
              onClick={() => switchPortal('user')}
            >
              👤 User
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={isAdmin}
              className={isAdmin ? 'on admin' : ''}
              onClick={() => switchPortal('admin')}
            >
              🛡️ Admin
            </button>
          </div>

          <div className="auth-heading">
            <h3>
              {isAdmin
                ? 'Admin portal'
                : mode === 'signup'
                  ? 'Create your account'
                  : mode === 'otp'
                    ? 'Verify your phone'
                    : mode === 'forgot'
                      ? 'Reset your password'
                      : 'Welcome back'}
            </h3>
            <p>
              {isAdmin
                ? 'Restricted access. Admin credentials only.'
                : mode === 'signup'
                  ? 'One-time phone verification, then password only.'
                  : mode === 'otp'
                    ? 'Enter the code we texted you.'
                    : mode === 'forgot'
                      ? "We'll text a code to your registered number."
                      : 'Sign in to your hackathon dashboard.'}
            </p>
          </div>

          {!isAdmin && mode !== 'otp' && mode !== 'forgot' && (
            <div className="auth-tabs">
              <button
                type="button"
                className={mode === 'signin' ? 'on' : ''}
                onClick={() => goTo('signin')}
              >
                Sign in
              </button>
              <button
                type="button"
                className={mode === 'signup' ? 'on' : ''}
                onClick={() => goTo('signup')}
              >
                Create account
              </button>
            </div>
          )}

          {error && <div className="error-banner">⚠ {error}</div>}
          {notice && !error && <div className="notice-banner">{notice}</div>}

          {otp?.dev_code && mode === 'otp' && (
            <div className="dev-banner">
              <strong>Development mode — no SMS was sent.</strong>
              <div className="dev-code">{otp.dev_code}</div>
              <span>
                Also printed in the backend terminal. Configure an SMS provider in{' '}
                <code>.env</code> to deliver real messages.
              </span>
            </div>
          )}

          <form onSubmit={submit}>
            {mode === 'signup' && (
              <div className="field">
                <label>Full name</label>
                <input
                  type="text"
                  value={form.name}
                  autoComplete="name"
                  placeholder="Madhusudhan R"
                  onChange={(event) => set({ name: event.target.value })}
                  required
                />
              </div>
            )}

            <div className="field">
              <label>Username</label>
              <input
                type="text"
                value={form.username}
                autoComplete="username"
                placeholder={isAdmin ? 'admin' : 'madhu'}
                disabled={mode === 'otp'}
                onChange={(event) => onUsernameChange(event.target.value)}
                required
              />
              {mode === 'signup' && usernameHint && (
                <p className={`field-hint ${usernameHint.available ? 'ok' : 'bad'}`}>
                  {usernameHint.available
                    ? `✓ "${usernameHint.username}" is available`
                    : `✗ ${usernameHint.reason}`}
                </p>
              )}
            </div>

            {mode === 'signup' && (
              <div className="field">
                <label>Phone number</label>
                <input
                  type="tel"
                  value={form.phone}
                  autoComplete="tel"
                  placeholder="+91 98765 43210"
                  onChange={(event) => set({ phone: event.target.value })}
                  required
                />
                <p className="field-hint">
                  We text a one-time code here. You will not need a code again
                  after this.
                </p>
              </div>
            )}

            {(mode === 'signin' || mode === 'signup') && (
              <div className="field">
                <label>Password</label>
                <input
                  type="password"
                  value={form.password}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  placeholder={mode === 'signup' ? 'At least 8 characters' : ''}
                  onChange={(event) => set({ password: event.target.value })}
                  required
                />
              </div>
            )}

            {mode === 'otp' && (
              <>
                <div className="field">
                  <label>Verification code</label>
                  <input
                    className="otp-input"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={form.code}
                    placeholder="······"
                    onChange={(event) => set({ code: event.target.value.replace(/\D/g, '') })}
                    required
                  />
                </div>

                {otpPurpose === 'reset' && (
                  <div className="field">
                    <label>New password</label>
                    <input
                      type="password"
                      value={form.newPassword}
                      autoComplete="new-password"
                      placeholder="At least 8 characters"
                      onChange={(event) => set({ newPassword: event.target.value })}
                      required
                    />
                  </div>
                )}

                <div className="auth-row">
                  <button
                    type="button"
                    className="link-btn"
                    disabled={resendIn > 0 || busy}
                    onClick={doResend}
                  >
                    {resendIn > 0 ? `Resend code in ${resendIn}s` : 'Resend code'}
                  </button>
                  <button type="button" className="link-btn" onClick={() => goTo('signin')}>
                    Back to sign in
                  </button>
                </div>
              </>
            )}

            <button
              className={`btn auth-submit ${isAdmin ? 'admin' : 'primary'}`}
              type="submit"
              disabled={busy}
            >
              {busy && <span className="spinner" />}
              {submitLabel}
            </button>
          </form>

          {mode === 'signin' && !isAdmin && (
            <button type="button" className="link-btn auth-forgot" onClick={() => goTo('forgot')}>
              Forgot password?
            </button>
          )}

          {mode === 'forgot' && (
            <p className="auth-note">
              <button type="button" className="link-btn" onClick={() => goTo('signin')}>
                ← Back to sign in
              </button>
            </p>
          )}

          {isAdmin && (
            <p className="auth-note admin-note">
              Admin accounts are created from the server, not here:
              <code>manage.py create-admin</code>
            </p>
          )}
        </section>
      </div>
    </div>
  )
}

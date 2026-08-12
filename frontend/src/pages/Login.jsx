import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'

/**
 * One screen, four modes:
 *   signin  — username + password (no OTP; this is the everyday path)
 *   signup  — details, then a one-time OTP to verify the phone
 *   otp     — enter the code (registration or password reset)
 *   forgot  — request a reset code, then set a new password
 */
export default function Login() {
  const { signIn } = useAuth()
  const [mode, setMode] = useState('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [form, setForm] = useState({
    name: '',
    username: '',
    phone: '',
    password: '',
    code: '',
    newPassword: '',
  })

  // Details about the OTP we just sent (masked phone, dev code, resend timer).
  const [otp, setOtp] = useState(null)
  const [otpPurpose, setOtpPurpose] = useState('register')
  const [resendIn, setResendIn] = useState(0)
  const [usernameHint, setUsernameHint] = useState(null)
  const usernameTimer = useRef(null)

  const set = (patch) => setForm((current) => ({ ...current, ...patch }))

  useEffect(() => {
    if (resendIn <= 0) return undefined
    const timer = setTimeout(() => setResendIn((value) => value - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  const goTo = (nextMode) => {
    setMode(nextMode)
    setError('')
    setNotice('')
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

  // --- live username availability ------------------------------------
  const onUsernameChange = (value) => {
    set({ username: value })
    setUsernameHint(null)
    clearTimeout(usernameTimer.current)
    if (mode !== 'signup' || value.trim().length < 3) return
    usernameTimer.current = setTimeout(() => {
      api
        .checkUsername(value)
        .then(setUsernameHint)
        .catch(() => setUsernameHint(null))
    }, 400)
  }

  const startOtp = (result, purpose) => {
    setOtp(result)
    setOtpPurpose(purpose)
    setResendIn(result.resend_in || 60)
    setMode('otp')
    setNotice(`We sent a ${'' + (result.dev_code || '').length || 6}-digit code to ${result.phone_masked}.`)
  }

  // --- actions ---------------------------------------------------------

  const doSignIn = () =>
    run(async () => {
      const result = await api.login(form.username, form.password)
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
      if (otpPurpose === 'register') {
        const result = await api.verifyOtp(form.username, form.code)
        signIn(result.token, result.user)
      } else {
        const result = await api.resetPassword(form.username, form.code, form.newPassword)
        signIn(result.token, result.user)
      }
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

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="brand" style={{ justifyContent: 'center' }}>
          <div className="brand-mark">📡</div>
          <h1>HackRadar</h1>
        </div>
        <p className="auth-tag">One place for every hackathon</p>

        {mode !== 'otp' && (
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
              Your code is also printed in the backend terminal. Configure an SMS
              provider in <code>.env</code> to deliver real messages.
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
              placeholder="madhu"
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
                We send a one-time code here to verify it. You will not need a code
                again after this.
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

          <button className="btn primary auth-submit" type="submit" disabled={busy}>
            {busy
              ? 'Please wait…'
              : mode === 'signin'
                ? 'Sign in'
                : mode === 'signup'
                  ? 'Send verification code'
                  : mode === 'otp'
                    ? otpPurpose === 'reset'
                      ? 'Reset password'
                      : 'Verify and continue'
                    : 'Send reset code'}
          </button>
        </form>

        {mode === 'signin' && (
          <button type="button" className="link-btn auth-forgot" onClick={() => goTo('forgot')}>
            Forgot password?
          </button>
        )}

        {mode === 'forgot' && (
          <p className="auth-note">
            Enter your username and we'll text a reset code to the phone number on
            the account.{' '}
            <button type="button" className="link-btn" onClick={() => goTo('signin')}>
              Back to sign in
            </button>
          </p>
        )}
      </div>
    </div>
  )
}

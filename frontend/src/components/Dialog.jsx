import { useEffect, useRef, useState } from 'react'

/**
 * Styled replacements for window.confirm() and window.prompt().
 *
 * Both trap Escape, close on backdrop click, and focus the primary control
 * on open — none of which the native dialogs allow you to control.
 */

function Shell({ title, children, onClose }) {
  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="dialog-title">{title}</h2>
        {children}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  danger = false,
  busy = false,
  onConfirm,
  onClose,
}) {
  const confirmRef = useRef(null)
  useEffect(() => confirmRef.current?.focus(), [])

  return (
    <Shell title={title} onClose={onClose}>
      <p className="dialog-message">{message}</p>
      <div className="modal-actions">
        <button className="btn" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button
          ref={confirmRef}
          className={`btn ${danger ? 'danger' : 'primary'}`}
          onClick={onConfirm}
          disabled={busy}
        >
          {busy && <span className="spinner" />}
          {confirmLabel}
        </button>
      </div>
    </Shell>
  )
}

export function PromptDialog({
  title,
  message,
  label,
  placeholder = '',
  confirmLabel = 'Save',
  type = 'text',
  busy = false,
  validate,
  onSubmit,
  onClose,
}) {
  const [value, setValue] = useState('')
  const [problem, setProblem] = useState('')
  const inputRef = useRef(null)

  useEffect(() => inputRef.current?.focus(), [])

  const submit = (event) => {
    event.preventDefault()
    const complaint = validate ? validate(value) : ''
    if (complaint) {
      setProblem(complaint)
      return
    }
    onSubmit(value)
  }

  return (
    <Shell title={title} onClose={onClose}>
      {message && <p className="dialog-message">{message}</p>}
      <form onSubmit={submit}>
        <div className="field">
          <label>{label}</label>
          <input
            ref={inputRef}
            type={type}
            value={value}
            placeholder={placeholder}
            onChange={(event) => {
              setValue(event.target.value)
              setProblem('')
            }}
          />
          {problem && <p className="field-hint bad">{problem}</p>}
        </div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn primary" disabled={busy}>
            {busy && <span className="spinner" />}
            {confirmLabel}
          </button>
        </div>
      </form>
    </Shell>
  )
}

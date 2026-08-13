import { createContext, useCallback, useContext, useEffect, useState } from 'react'

/**
 * Toast notifications.
 *
 *   const toast = useToast()
 *   toast.success('Profile saved')
 *   toast.error('Could not reach the server')
 *
 * Replaces the browser's alert(), which cannot be styled and blocks the
 * whole page.
 */

const ToastContext = createContext(null)

let nextId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((message, kind = 'info', duration = 4000) => {
    const id = (nextId += 1)
    setToasts((current) => [...current, { id, message, kind, duration }])
    return id
  }, [])

  const api = {
    push,
    dismiss,
    success: useCallback((m, d) => push(m, 'success', d), [push]),
    error: useCallback((m, d) => push(m, 'error', d ?? 6000), [push]),
    info: useCallback((m, d) => push(m, 'info', d), [push]),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    // Start the exit animation slightly before removal so it can play out.
    const exitAt = Math.max(toast.duration - 260, 100)
    const exitTimer = setTimeout(() => setLeaving(true), exitAt)
    const killTimer = setTimeout(() => onDismiss(toast.id), toast.duration)
    return () => {
      clearTimeout(exitTimer)
      clearTimeout(killTimer)
    }
  }, [toast, onDismiss])

  const icon = { success: '✓', error: '⚠', info: 'ℹ' }[toast.kind] || 'ℹ'

  return (
    <div className={`toast ${toast.kind} ${leaving ? 'leaving' : ''}`}>
      <span className="toast-icon">{icon}</span>
      <span className="toast-body">{toast.message}</span>
      <button className="toast-close" onClick={() => onDismiss(toast.id)} aria-label="Dismiss">
        ×
      </button>
    </div>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}

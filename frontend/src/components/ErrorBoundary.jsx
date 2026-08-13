import { Component } from 'react'

/**
 * Catches render errors so a single bad component shows a recovery panel
 * instead of a blank white page.
 *
 * Must be a class — React has no hook equivalent for componentDidCatch.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Wire this to Sentry or similar when you deploy.
    console.error('Unhandled UI error:', error, info?.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="crash-screen">
        <div className="crash-card">
          <div className="crash-icon">💥</div>
          <h1>Something broke on this screen</h1>
          <p>
            The rest of the app is fine — this view hit an error while rendering.
            Reloading usually clears it.
          </p>

          <details>
            <summary>Technical details</summary>
            <pre>{error?.message || String(error)}</pre>
          </details>

          <div className="crash-actions">
            <button className="btn primary" onClick={() => window.location.reload()}>
              Reload the page
            </button>
            <button
              className="btn"
              onClick={() => {
                window.location.href = '/'
              }}
            >
              Back to dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }
}

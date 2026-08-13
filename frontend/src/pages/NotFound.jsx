import { Link, useLocation } from 'react-router-dom'
import RadarMark from '../components/RadarMark'

export default function NotFound() {
  const { pathname } = useLocation()

  return (
    <div className="empty not-found">
      <RadarMark size={52} />
      <h2>Nothing on this frequency</h2>
      <p>
        No page matches <code>{pathname}</code>.
      </p>
      <div className="crash-actions">
        <Link className="btn primary" to="/">
          Back to Discover
        </Link>
        <Link className="btn" to="/deadlines">
          See deadlines
        </Link>
      </div>
    </div>
  )
}

import { Link } from 'react-router-dom';
import { Icon } from '../components/Icons';

export function NotFoundPage() {
  return (
    <div className="notfound">
      <div className="notfound-mark">
        <Icon name="gate" size={34} />
      </div>
      <span className="eyebrow">404</span>
      <h1>This path is not part of the control plane.</h1>
      <p>The page may have moved, or the link may be incomplete.</p>
      <div className="notfound-actions">
        <Link to="/" className="btn btn-outline">
          Product site
        </Link>
        <Link to="/app" className="btn btn-primary">
          Open the app <Icon name="arrow-right" size={16} />
        </Link>
      </div>
    </div>
  );
}

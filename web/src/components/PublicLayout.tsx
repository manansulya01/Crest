import { Link, NavLink, Outlet } from 'react-router-dom';
import { Icon } from './Icons';
import { ThemeToggle } from './ThemeToggle';

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M7 23 14 9l4 7 2.5-4L25 23H7Z" fill="var(--accent-contrast)" opacity="0.95" />
      <path d="M14 9l2.2 3.9" stroke="var(--accent)" strokeWidth="1.4" />
    </svg>
  );
}

export function PublicLayout() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="site-header-inner">
          <Link to="/" className="brand-link">
            <BrandMark />
            <span>
              <strong>CREST</strong>
              <small>Outcome-constrained inference</small>
            </span>
          </Link>
          <nav className="site-nav" aria-label="Product">
            <NavLink to="/docs" className={({ isActive }) => (isActive ? 'active' : '')}>
              Docs
            </NavLink>
            <NavLink to="/security" className={({ isActive }) => (isActive ? 'active' : '')}>
              Security
            </NavLink>
            <a
              href="https://github.com/manansulya01/Crest"
              target="_blank"
              rel="noreferrer"
              className="site-nav-github"
            >
              <Icon name="github" size={16} /> GitHub
            </a>
          </nav>
          <div className="site-header-actions">
            <ThemeToggle />
            <Link to="/app" className="btn btn-primary btn-sm">
              Open app <Icon name="arrow-right" size={15} />
            </Link>
          </div>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <div className="footer-brand">
            <BrandMark />
            <div>
              <strong>CREST 1.0</strong>
              <p>Learning proposes. Evidence certifies. The constitution grants. Observation can revoke.</p>
            </div>
          </div>
          <div className="footer-columns">
            <div>
              <h4>Product</h4>
              <Link to="/app">Open the app</Link>
              <Link to="/docs">Documentation</Link>
              <Link to="/security">Security model</Link>
            </div>
            <div>
              <h4>Research</h4>
              <a href="https://github.com/manansulya01/Crest" target="_blank" rel="noreferrer">
                Repository
              </a>
              <a
                href="https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/CREST_RESEARCH_BOOK.md"
                target="_blank"
                rel="noreferrer"
              >
                Research book
              </a>
              <a
                href="https://github.com/manansulya01/Crest/blob/feat/crest-1.0-product/docs/CREST_1_0_INSTALLATION.md"
                target="_blank"
                rel="noreferrer"
              >
                Installation guide
              </a>
            </div>
          </div>
        </div>
        <div className="site-footer-bottom">
          <span>© {new Date().getFullYear()} CREST. Local-first, open source.</span>
          <span>
            Security posture: Level 3 — supervised personal use. Not a production safety guarantee.
          </span>
        </div>
      </footer>
    </div>
  );
}

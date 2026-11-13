import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import type { IconName } from '../components/Icons';
import { ThemeToggle } from '../components/ThemeToggle';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}

const groups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: 'Workspace',
    items: [
      { to: '/app', label: 'Dashboard', icon: 'dashboard', end: true },
      { to: '/app/tasks', label: 'Tasks', icon: 'tasks' },
      { to: '/app/approvals', label: 'Approvals', icon: 'shield' },
    ],
  },
  {
    label: 'Control',
    items: [
      { to: '/app/autonomy', label: 'Autonomy', icon: 'layers' },
      { to: '/app/providers', label: 'Providers', icon: 'providers' },
      { to: '/app/routing', label: 'Routing', icon: 'route' },
      { to: '/app/budgets', label: 'Budgets', icon: 'budget' },
    ],
  },
  {
    label: 'Evidence',
    items: [
      { to: '/app/evidence', label: 'Evidence', icon: 'evidence' },
      { to: '/app/audit', label: 'Audit log', icon: 'audit' },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/app/demos', label: 'Offline demos', icon: 'flask' },
      { to: '/app/settings', label: 'Settings', icon: 'settings' },
      { to: '/app/system', label: 'System', icon: 'system' },
    ],
  },
];

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M7 23 14 9l4 7 2.5-4L25 23H7Z" fill="var(--accent-contrast)" opacity="0.95" />
      <path d="M14 9l2.2 3.9" stroke="var(--accent)" strokeWidth="1.4" />
    </svg>
  );
}

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const health = useApi(() => api.health(), [], { pollMs: 30000 });

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  return (
    <div className={`app-shell ${open ? 'nav-open' : ''}`.trim()}>
      <button
        type="button"
        className="nav-overlay"
        aria-label="Close navigation"
        onClick={() => setOpen(false)}
      />
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Link to="/app" className="brand-link">
            <BrandMark />
            <span>
              <strong>CREST</strong>
              <small>Inference control plane</small>
            </span>
          </Link>
          <button
            type="button"
            className="btn btn-icon btn-ghost sidebar-close"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Application">
          {groups.map((group) => (
            <div key={group.label} className="nav-group">
              <div className="nav-group-label">{group.label}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`.trim()}
                >
                  <Icon name={item.icon} size={17} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="local-status">
            <span
              className={`status-dot ${
                health.error ? 'status-dot-offline' : health.data ? 'status-dot-online' : ''
              }`.trim()}
            />
            <div>
              <strong>{health.error ? 'API unreachable' : health.data ? 'API online' : 'Connecting…'}</strong>
              <small>Local · v{health.data?.version ?? '1.0.0'}</small>
            </div>
          </div>
          <Link to="/" className="sidebar-site-link">
            <Icon name="external" size={14} /> Product site
          </Link>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="btn btn-icon btn-ghost menu-button"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Icon name="menu" size={20} />
            </button>
            <span className="topbar-title">Control plane</span>
            <span className="topbar-divider" />
            <span className="topbar-context">
              <Icon name="lock" size={14} /> Local-first · supervised use
            </span>
          </div>
          <div className="topbar-right">
            <ThemeToggle />
            <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
              <Icon name="plus" size={16} /> New task
            </Link>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

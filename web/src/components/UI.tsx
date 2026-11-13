import type { ReactNode } from 'react';
import { Icon } from './Icons';
import type { IconName } from './Icons';
import { useToast } from '../lib/toast';
import { gateTone, riskTone, statusTone, titleCase } from '../lib/format';

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = '',
  padded = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={`card ${className}`.trim()}>
      {title || actions ? (
        <div className="card-header">
          <div>
            {title ? <h2 className="card-title">{title}</h2> : null}
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? 'card-body' : 'card-body card-body-flush'}>{children}</div>
    </section>
  );
}

export type Tone = 'success' | 'danger' | 'warn' | 'info' | 'neutral' | 'accent';

export function Badge({
  children,
  tone = 'neutral',
  dot = false,
  className = '',
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={`badge tone-${tone} ${className}`.trim()}>
      {dot ? <span className="badge-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const value = status || 'unknown';
  return (
    <Badge tone={statusTone(value) as Tone} dot>
      {label ?? titleCase(value)}
    </Badge>
  );
}

export function RiskBadge({ risk }: { risk: string | null | undefined }) {
  return (
    <Badge tone={riskTone(risk) as Tone} className="badge-outline">
      {risk ? `${titleCase(risk)} risk` : 'No risk'}
    </Badge>
  );
}

export function GateBadge({ decision }: { decision: string | null | undefined }) {
  if (!decision) return <span className="muted">—</span>;
  return <Badge tone={gateTone(decision) as Tone}>{decision}</Badge>;
}

export function Spinner({ size = 18 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-label="Loading" />;
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-block">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="skeleton-rows" aria-label="Loading content">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton skeleton-row" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon = 'layers',
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon name={icon} size={26} />
      </div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <div className="error-icon">
        <Icon name="alert" size={22} />
      </div>
      <div>
        <strong>Something went wrong</strong>
        <p>{message}</p>
        {onRetry ? (
          <button type="button" className="btn btn-sm btn-outline" onClick={onRetry}>
            <Icon name="refresh" size={15} /> Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function InlineNotice({
  tone = 'info',
  title,
  children,
  icon = 'info',
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
  icon?: IconName;
}) {
  return (
    <div className={`notice notice-${tone}`}>
      <Icon name={icon} size={18} />
      <div>
        {title ? <strong>{title}</strong> : null}
        <div className="notice-body">{children}</div>
      </div>
    </div>
  );
}

export function Progress({
  value,
  max,
  tone = 'accent',
  label,
}: {
  value: number;
  max: number;
  tone?: 'accent' | 'warn' | 'danger' | 'success';
  label?: string;
}) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div className="progress-wrap">
      <div
        className={`progress progress-${tone}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={label ?? 'Usage'}
      >
        <span style={{ width: `${ratio * 100}%` }} />
      </div>
      {label ? <span className="progress-label">{label}</span> : null}
    </div>
  );
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const { notify } = useToast();
  return (
    <button
      type="button"
      className="btn btn-xs btn-ghost"
      onClick={() => {
        void navigator.clipboard
          .writeText(value)
          .then(() => notify('Copied to clipboard.', 'success'))
          .catch(() => notify('Clipboard is unavailable in this browser.', 'error'));
      }}
    >
      <Icon name="copy" size={13} /> {label}
    </button>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="pagination">
      <span className="muted">
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="pagination-buttons">
        <button
          type="button"
          className="btn btn-sm btn-outline"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <span className="pagination-page">
          Page {page} / {pages}
        </span>
        <button
          type="button"
          className="btn btn-sm btn-outline"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function MetaList({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="meta-list">
      {items.map((item) => (
        <div key={item.label} className="meta-row">
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function StatCard({
  label,
  value,
  detail,
  tone = 'neutral',
  icon,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: Tone;
  icon?: IconName;
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        {icon ? (
          <span className="stat-icon">
            <Icon name={icon} size={17} />
          </span>
        ) : null}
      </div>
      <div className="stat-value">{value}</div>
      {detail ? <div className="stat-detail">{detail}</div> : null}
    </div>
  );
}

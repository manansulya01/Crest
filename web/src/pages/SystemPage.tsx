import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatBytes, formatDateTime, formatNumber, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import {
  Badge,
  Card,
  ErrorState,
  InlineNotice,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from '../components/UI';

export function SystemPage() {
  const diagnostics = useApi(() => api.diagnostics(), [], { pollMs: 30000 });

  const data = diagnostics.data;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="System diagnostics"
        description="Runtime, database, provider, and safety state for this local installation. No telemetry leaves the machine."
        actions={
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={diagnostics.reload}
            disabled={diagnostics.loading}
          >
            <Icon name="refresh" size={15} /> Refresh
          </button>
        }
      />

      {diagnostics.error ? <ErrorState message={diagnostics.error} onRetry={diagnostics.reload} /> : null}
      {diagnostics.loading && !data ? <LoadingBlock label="Loading diagnostics…" /> : null}

      {data ? (
        <>
          {!data.database.integrity.ok ? (
            <InlineNotice tone="danger" title="Database integrity check failed" icon="alert">
              Stop the application and inspect the database before continuing. Result:{' '}
              {data.database.integrity.result.join(', ')}
            </InlineNotice>
          ) : null}

          <div className="system-grid">
            <Card title="Application">
              <dl className="meta-list compact">
                <div className="meta-row">
                  <dt>Status</dt>
                  <dd>
                    <StatusBadge status={data.status} />
                  </dd>
                </div>
                <div className="meta-row">
                  <dt>Version</dt>
                  <dd>CREST {data.version}</dd>
                </div>
                <div className="meta-row">
                  <dt>Schema</dt>
                  <dd>v{data.schema_version}</dd>
                </div>
                <div className="meta-row">
                  <dt>Operating mode</dt>
                  <dd>{data.control?.operating_mode ?? '—'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Execution</dt>
                  <dd>{data.control?.paused ? 'Paused' : 'Running'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Started</dt>
                  <dd>{formatDateTime(data.started_at)}</dd>
                </div>
                <div className="meta-row">
                  <dt>Uptime</dt>
                  <dd>{Math.floor(data.uptime_seconds / 60)} min</dd>
                </div>
                <div className="meta-row">
                  <dt>Python</dt>
                  <dd>{data.python}</dd>
                </div>
                <div className="meta-row">
                  <dt>Platform</dt>
                  <dd className="wrap-anywhere">{data.platform}</dd>
                </div>
                <div className="meta-row">
                  <dt>Data directory</dt>
                  <dd className="mono wrap-anywhere">{data.data_dir}</dd>
                </div>
              </dl>
            </Card>

            <Card title="Safety posture">
              <div className="posture">
                <Badge tone="warn">Level 3 — supervised personal use</Badge>
                <p>
                  CREST is not a production safety guarantee. Evidence is content-addressed but not a
                  signed attestation. High-risk acceptance requires independent evidence; with
                  mock-only evidence the gate abstains.
                </p>
              </div>
              <dl className="meta-list compact">
                <div className="meta-row">
                  <dt>External calls</dt>
                  <dd>
                    <Badge tone={data.external_calls_enabled ? 'warn' : 'success'}>
                      {data.external_calls_enabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                  </dd>
                </div>
                <div className="meta-row">
                  <dt>API token</dt>
                  <dd>{data.auth_token_required ? 'Required' : 'Not required'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Frontend built</dt>
                  <dd>{data.frontend_built ? 'Yes' : 'No — run npm run build'}</dd>
                </div>
                <div className="meta-row">
                  <dt>API docs</dt>
                  <dd>
                    <a href="/api/docs" target="_blank" rel="noreferrer" className="inline-link">
                      OpenAPI / Swagger <Icon name="external" size={12} />
                    </a>
                  </dd>
                </div>
              </dl>
            </Card>
          </div>

          <Card
            title="Database"
            subtitle="SQLite in WAL mode with foreign keys and busy timeout"
            actions={
              <Badge tone={data.database.integrity.ok ? 'success' : 'danger'}>
                Integrity {data.database.integrity.ok ? 'OK' : 'failed'}
              </Badge>
            }
          >
            <div className="db-grid">
              <div className="db-path">
                <span className="field-label">Database file</span>
                <code className="inline-code wrap-anywhere">{data.database.path}</code>
                <span className="muted">{formatBytes(data.database.size_bytes)}</span>
              </div>
              <div className="count-grid">
                {Object.entries(data.database.counts).map(([table, count]) => (
                  <div key={table} className="count-cell">
                    <span>{titleCase(table)}</span>
                    <strong>{formatNumber(count)}</strong>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card
            title="Providers"
            subtitle="Configuration state only; credentials remain in environment variables"
            actions={
              <Link to="/app/providers" className="btn btn-xs btn-outline">
                Manage providers
              </Link>
            }
          >
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Kind</th>
                    <th>Enabled</th>
                    <th>Status</th>
                    <th>Key</th>
                    <th>Default model</th>
                    <th>Last test</th>
                  </tr>
                </thead>
                <tbody>
                  {data.providers.map((provider) => (
                    <tr key={provider.id}>
                      <td>
                        <strong>{provider.name}</strong>
                      </td>
                      <td className="muted">{provider.kind}</td>
                      <td>{provider.enabled ? 'Yes' : 'No'}</td>
                      <td>
                        <StatusBadge status={provider.status} />
                      </td>
                      <td>
                        {provider.external ? (
                          <Badge tone={provider.key_present ? 'success' : 'warn'}>
                            {provider.key_present ? 'Present' : 'Missing'}
                          </Badge>
                        ) : (
                          <span className="muted">Not required</span>
                        )}
                      </td>
                      <td className="mono">{provider.default_model}</td>
                      <td className="muted">{provider.last_test_at ? formatDateTime(provider.last_test_at) : 'Never'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="two-col">
            <Card title="Windows data locations" subtitle="All persistent state lives under the application data directory">
              <dl className="meta-list compact">
                <div className="meta-row">
                  <dt>Data</dt>
                  <dd className="mono wrap-anywhere">{data.paths?.data_dir ?? '—'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Database</dt>
                  <dd className="mono wrap-anywhere">{data.paths?.database ?? '—'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Logs</dt>
                  <dd className="mono wrap-anywhere">{data.paths?.logs ?? '—'}</dd>
                </div>
                <div className="meta-row">
                  <dt>Backups</dt>
                  <dd className="mono wrap-anywhere">{data.paths?.backups ?? '—'}</dd>
                </div>
              </dl>
              <p className="page-note">
                <Icon name="info" size={15} />
                <span>
                  Uninstalling the app never removes this directory. Delete it manually only when you
                  intend to discard all local data.
                </span>
              </p>
            </Card>

            <Card title="Credential storage" subtitle="Secrets are encrypted at rest and never returned by the API">
              <dl className="meta-list compact">
                <div className="meta-row">
                  <dt>Backend</dt>
                  <dd><Badge tone={data.credentials?.windows_dpapi ? 'success' : 'info'}>{data.credentials?.backend ?? '—'}</Badge></dd>
                </div>
                <div className="meta-row">
                  <dt>Detail</dt>
                  <dd className="wrap-anywhere">{data.credentials?.detail ?? '—'}</dd>
                </div>
                {data.credentials?.providers.map((item) => (
                  <div className="meta-row" key={item.provider_id}>
                    <dt>{item.name}</dt>
                    <dd>{item.configured ? item.source : 'Not configured'}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          </div>

          <Card
            title="Log files"
            subtitle="Rotating, redacted logs. Secret material is masked before it is written."
            actions={
              <Link to="/app/settings" className="btn btn-xs btn-outline">
                Log retention
              </Link>
            }
          >
            {data.logs?.files.length ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>File</th><th>Size</th></tr></thead>
                  <tbody>
                    {data.logs.files.map((file) => (
                      <tr key={file.name}>
                        <td className="mono">{file.name}</td>
                        <td>{formatBytes(file.size_bytes)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">No log files yet.</p>
            )}
          </Card>

          <div className="two-col">
            <Card title="Restart and interruption behavior">
              <ul className="plain-list">
                <li>
                  <Icon name="check" size={15} /> Executions are persisted before they start.
                </li>
                <li>
                  <Icon name="check" size={15} /> On startup, queued or running executions are marked
                  interrupted, never completed.
                </li>
                <li>
                  <Icon name="check" size={15} /> Task records and audit history survive restarts.
                </li>
                <li>
                  <Icon name="check" size={15} /> The web dashboard polls task state; closing the
                  browser does not cancel server-side work.
                </li>
              </ul>
            </Card>

            <Card title="Local-first guarantees">
              <ul className="plain-list">
                <li>
                  <Icon name="lock" size={15} /> Binds to localhost by default; host allowlist is
                  enforced.
                </li>
                <li>
                  <Icon name="lock" size={15} /> Stored provider keys are encrypted with Windows DPAPI
                  and never returned, logged, or exported.
                </li>
                <li>
                  <Icon name="lock" size={15} /> No analytics, telemetry, or remote logging is
                  included.
                </li>
                <li>
                  <Icon name="lock" size={15} /> Security headers and optional bearer authentication
                  are applied by the API.
                </li>
              </ul>
            </Card>
          </div>

          <p className="page-note">
            <Icon name="info" size={15} />
            <span>
              This page reports the live state returned by <code className="inline-code">/api/v1/diagnostics</code>.
              It does not perform additional checks beyond the database integrity query.
            </span>
          </p>
        </>
      ) : null}
    </>
  );
}

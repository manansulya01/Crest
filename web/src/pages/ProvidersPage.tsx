import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatDateTime, formatNumber, relativeTime, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { Provider } from '../lib/types';
import { Icon } from '../components/Icons';
import { Modal } from '../components/Modal';
import {
  Badge,
  Card,
  ErrorState,
  InlineNotice,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from '../components/UI';

interface Draft {
  name: string;
  enabled: boolean;
  base_url: string;
  api_key_env: string;
  default_model: string;
  models: string;
  input_cost_per_1k: string;
  output_cost_per_1k: string;
  max_output_tokens: string;
  timeout_seconds: string;
  retry_max: string;
  rate_limit_per_minute: string;
}

function draftFrom(provider: Provider): Draft {
  return {
    name: provider.name,
    enabled: provider.enabled,
    base_url: provider.base_url,
    api_key_env: provider.api_key_env,
    default_model: provider.default_model,
    models: provider.models.join(', '),
    input_cost_per_1k: String(provider.input_cost_per_1k),
    output_cost_per_1k: String(provider.output_cost_per_1k),
    max_output_tokens: String(provider.max_output_tokens),
    timeout_seconds: String(provider.timeout_seconds),
    retry_max: String(provider.retry_max ?? 2),
    rate_limit_per_minute: String(provider.rate_limit_per_minute ?? 30),
  };
}

export function ProvidersPage() {
  const { notify } = useToast();
  const providers = useApi(() => api.providers.list(), []);
  const settings = useApi(() => api.settings.get(), []);
  const credentials = useApi(() => api.credentials.status(), []);
  const [usageProvider, setUsageProvider] = useState('');
  const usage = useApi(() => api.providers.usage(usageProvider), [usageProvider], {
    enabled: Boolean(usageProvider),
  });
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testTarget, setTestTarget] = useState<Provider | null>(null);
  const [testResults, setTestResults] = useState<Record<string, Record<string, unknown>>>({});
  const [keyTarget, setKeyTarget] = useState<Provider | null>(null);
  const [keyDraft, setKeyDraft] = useState('');

  function startEdit(provider: Provider) {
    setEditing(provider.id);
    setDraft(draftFrom(provider));
    setError(null);
  }

  function reloadAll() {
    providers.reload();
    credentials.reload();
  }

  async function save(provider: Provider) {
    if (!draft) return;
    setBusy(`save-${provider.id}`);
    setError(null);
    try {
      await api.providers.update(provider.id, {
        name: draft.name.trim(),
        enabled: draft.enabled,
        base_url: draft.base_url.trim(),
        api_key_env: draft.api_key_env.trim(),
        default_model: draft.default_model.trim(),
        models: draft.models.split(',').map((item) => item.trim()).filter(Boolean),
        input_cost_per_1k: Number(draft.input_cost_per_1k),
        output_cost_per_1k: Number(draft.output_cost_per_1k),
        max_output_tokens: Number(draft.max_output_tokens),
        timeout_seconds: Number(draft.timeout_seconds),
        retry_max: Number(draft.retry_max),
        rate_limit_per_minute: Number(draft.rate_limit_per_minute),
      });
      notify(`${provider.name} updated.`, 'success');
      setEditing(null);
      setDraft(null);
      providers.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function test(provider: Provider) {
    setBusy(`test-${provider.id}`);
    setError(null);
    try {
      const result = await api.providers.test(provider.id, provider.default_model);
      setTestResults((current) => ({ ...current, [provider.id]: result }));
      notify(
        result.ok ? 'Connection test succeeded.' : 'Connection test failed. See the result below.',
        result.ok ? 'success' : 'error',
      );
      setTestTarget(null);
      providers.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setTestTarget(null);
    } finally {
      setBusy(null);
    }
  }

  async function saveKey() {
    if (!keyTarget || !keyDraft.trim()) return;
    setBusy(`key-${keyTarget.id}`);
    setError(null);
    try {
      const result = await api.credentials.set(keyTarget.id, keyDraft.trim());
      notify(`Credential stored with ${result.storage}. The key is never displayed again.`, 'success');
      setKeyDraft('');
      setKeyTarget(null);
      reloadAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function clearKey(provider: Provider) {
    setBusy(`key-${provider.id}`);
    setError(null);
    try {
      await api.credentials.clear(provider.id);
      notify('Stored credential removed.', 'success');
      reloadAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function discover(provider: Provider) {
    setBusy(`discover-${provider.id}`);
    setError(null);
    try {
      const result = await api.providers.discoverModels(provider.id);
      setEditing(provider.id);
      setDraft((current) => ({
        ...(current ?? draftFrom(provider)),
        models: result.models.join(', ') || (current?.models ?? ''),
      }));
      notify(`Discovered ${result.count} model${result.count === 1 ? '' : 's'}. Review and save.`, 'success');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  const externalEnabled = settings.data?.allow_external_calls ?? false;

  return (
    <>
      <PageHeader
        eyebrow="Control"
        title="Providers"
        description="Real provider adapters with explicit opt-in. Stored API keys are encrypted with Windows DPAPI (AES-GCM on non-Windows dev) and are never returned, logged, or exported."
        actions={
          <Link to="/app/settings" className="btn btn-outline btn-sm">
            <Icon name="settings" size={15} /> Call policy
          </Link>
        }
      />

      {credentials.data ? (
        <InlineNotice
          tone={credentials.data.windows_dpapi ? 'success' : 'info'}
          title={`Credential storage: ${credentials.data.backend}`}
          icon="key"
        >
          {credentials.data.detail} Environment-variable keys remain supported and take precedence
          only when no stored credential exists.
        </InlineNotice>
      ) : null}

      {providers.error ? <ErrorState message={providers.error} onRetry={providers.reload} /> : null}
      {credentials.error ? <ErrorState message={credentials.error} onRetry={credentials.reload} /> : null}
      {providers.loading && !providers.data ? <LoadingBlock label="Loading providers…" /> : null}

      {providers.data && !externalEnabled ? (
        <InlineNotice tone="info" title="External calls are disabled" icon="lock">
          The offline mock provider works without configuration. Gemini and OpenAI-compatible
          adapters exist, but execution, connection tests, and model discovery are blocked until
          external calls are explicitly enabled in <Link to="/app/settings">Settings</Link>.
        </InlineNotice>
      ) : null}

      {error ? (
        <InlineNotice tone="danger" title="Provider operation failed" icon="alert">
          {error}
        </InlineNotice>
      ) : null}

      <div className="provider-grid">
        {providers.data?.map((provider) => {
          const isEditing = editing === provider.id && draft;
          const result = testResults[provider.id];
          const credential = credentials.data?.providers.find((item) => item.provider_id === provider.id);
          return (
            <Card key={provider.id} className="provider-card">
              <div className="provider-head">
                <div className="provider-title">
                  <span className={`provider-logo provider-logo-${provider.kind}`}>
                    <Icon name={provider.kind === 'mock' ? 'flask' : 'spark'} size={20} />
                  </span>
                  <div>
                    <h2>{provider.name}</h2>
                    <span className="muted small">
                      {provider.kind === 'mock'
                        ? 'Deterministic offline adapter'
                        : provider.kind === 'gemini'
                          ? 'Google Gemini generateContent'
                          : 'OpenAI-compatible chat completions'}
                    </span>
                  </div>
                </div>
                <div className="provider-badges">
                  <StatusBadge status={provider.status} />
                  <Badge tone={provider.external ? 'warn' : 'success'}>
                    {provider.external ? 'External' : 'Offline'}
                  </Badge>
                </div>
              </div>

              <div className="provider-facts">
                <div>
                  <span className="field-label">Endpoint</span>
                  <code className="inline-code">{provider.base_url || 'No network endpoint'}</code>
                </div>
                <div>
                  <span className="field-label">API key environment</span>
                  <code className="inline-code">{provider.api_key_env || 'Not required'}</code>
                </div>
                <div>
                  <span className="field-label">Credential</span>
                  <Badge tone={provider.key_present ? 'success' : provider.external ? 'warn' : 'neutral'}>
                    {provider.external
                      ? provider.key_present
                        ? provider.credential_source === 'windows-dpapi'
                          ? 'Stored (DPAPI)'
                          : 'Environment'
                        : 'Missing'
                      : 'N/A'}
                  </Badge>
                </div>
                <div>
                  <span className="field-label">Default model</span>
                  <span className="mono">{provider.default_model}</span>
                </div>
                <div>
                  <span className="field-label">Configured models</span>
                  <span>{provider.models.join(', ') || 'None'}</span>
                </div>
                <div>
                  <span className="field-label">Retries / rate limit</span>
                  <span>{provider.retry_max} retries · {provider.rate_limit_per_minute}/min</span>
                </div>
                <div>
                  <span className="field-label">Pricing configured</span>
                  <span>
                    {provider.cost_configured
                      ? `$${provider.input_cost_per_1k}/1k in · $${provider.output_cost_per_1k}/1k out`
                      : 'Not configured (cost recorded as $0)'}
                  </span>
                </div>
                <div>
                  <span className="field-label">Last connection test</span>
                  <span>
                    {provider.last_test_status
                      ? `${titleCase(provider.last_test_status)} · ${relativeTime(provider.last_test_at)}`
                      : 'Never tested'}
                  </span>
                </div>
              </div>

              {provider.last_test_detail ? (
                <details className="provider-last-test">
                  <summary>Last test detail</summary>
                  <pre className="code-panel compact-code">{provider.last_test_detail}</pre>
                </details>
              ) : null}

              {credential?.updated_at ? (
                <p className="muted small">Credential updated {formatDateTime(credential.updated_at)}.</p>
              ) : null}

              {result ? (
                <InlineNotice
                  tone={result.ok ? 'success' : 'danger'}
                  title={result.ok ? 'Connection test succeeded' : 'Connection test failed'}
                  icon={result.ok ? 'check' : 'alert'}
                >
                  {String(result.message ?? '')}
                  {result.latency_ms !== undefined ? ` · ${result.latency_ms} ms` : ''}
                </InlineNotice>
              ) : null}

              {isEditing ? (
                <div className="provider-form">
                  <div className="form-grid">
                    <label className="field">
                      <span className="field-label">Display name</span>
                      <input className="input" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
                    </label>
                    <label className="checkbox-field provider-enabled">
                      <input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} />
                      <span>Enabled for routing</span>
                    </label>
                    <label className="field span-2">
                      <span className="field-label">Base URL</span>
                      <input className="input" value={draft.base_url} onChange={(event) => setDraft({ ...draft, base_url: event.target.value })} placeholder="https://…" />
                      <span className="field-hint">HTTPS is required except for localhost endpoints.</span>
                    </label>
                    <label className="field">
                      <span className="field-label">API key environment variable</span>
                      <input className="input" value={draft.api_key_env} onChange={(event) => setDraft({ ...draft, api_key_env: event.target.value })} placeholder="GEMINI_API_KEY" />
                      <span className="field-hint">Fallback only; stored credentials are preferred.</span>
                    </label>
                    <label className="field">
                      <span className="field-label">Default model</span>
                      <input className="input" value={draft.default_model} onChange={(event) => setDraft({ ...draft, default_model: event.target.value })} />
                    </label>
                    <label className="field span-2">
                      <span className="field-label">Models (comma separated)</span>
                      <input className="input" value={draft.models} onChange={(event) => setDraft({ ...draft, models: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Input cost per 1k tokens (USD)</span>
                      <input className="input" type="number" min="0" step="0.000001" value={draft.input_cost_per_1k} onChange={(event) => setDraft({ ...draft, input_cost_per_1k: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Output cost per 1k tokens (USD)</span>
                      <input className="input" type="number" min="0" step="0.000001" value={draft.output_cost_per_1k} onChange={(event) => setDraft({ ...draft, output_cost_per_1k: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Max output tokens</span>
                      <input className="input" type="number" min="1" value={draft.max_output_tokens} onChange={(event) => setDraft({ ...draft, max_output_tokens: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Timeout (seconds)</span>
                      <input className="input" type="number" min="1" max="600" value={draft.timeout_seconds} onChange={(event) => setDraft({ ...draft, timeout_seconds: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Max retries (0–5)</span>
                      <input className="input" type="number" min="0" max="5" value={draft.retry_max} onChange={(event) => setDraft({ ...draft, retry_max: event.target.value })} />
                    </label>
                    <label className="field">
                      <span className="field-label">Rate limit (requests/minute)</span>
                      <input className="input" type="number" min="1" max="600" value={draft.rate_limit_per_minute} onChange={(event) => setDraft({ ...draft, rate_limit_per_minute: event.target.value })} />
                    </label>
                  </div>
                  <div className="provider-form-actions">
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => { setEditing(null); setDraft(null); }} disabled={busy === `save-${provider.id}`}>Cancel</button>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => void save(provider)} disabled={busy === `save-${provider.id}`}>
                      {busy === `save-${provider.id}` ? 'Saving…' : 'Save provider'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="provider-actions">
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => startEdit(provider)}>
                    <Icon name="edit" size={15} /> Configure
                  </button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setTestTarget(provider)} disabled={busy === `test-${provider.id}`}>
                    <Icon name="spark" size={15} /> Test connection
                  </button>
                  {provider.external ? (
                    <>
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => { setKeyTarget(provider); setKeyDraft(''); }} disabled={busy === `key-${provider.id}`}>
                        <Icon name="key" size={15} /> {provider.key_present ? 'Replace key' : 'Set key'}
                      </button>
                      {provider.credential_source === 'windows-dpapi' ? (
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void clearKey(provider)} disabled={busy === `key-${provider.id}`}>
                          Clear stored key
                        </button>
                      ) : null}
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => void discover(provider)} disabled={busy === `discover-${provider.id}`}>
                        Discover models
                      </button>
                    </>
                  ) : null}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Card
        title="Provider usage history"
        subtitle="Every provider call, test, and rate-limit or error event is recorded with tokens, cost, and latency. Secrets are never stored here."
      >
        <div className="credential-inline" style={{ marginBottom: 14 }}>
          <label className="field" style={{ maxWidth: 320 }}>
            <span className="field-label">Provider</span>
            <select className="select" value={usageProvider} onChange={(event) => setUsageProvider(event.target.value)}>
              <option value="">Select a provider…</option>
              {providers.data?.map((provider) => (
                <option key={provider.id} value={provider.id}>{provider.name}</option>
              ))}
            </select>
          </label>
          {usageProvider ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={usage.reload}><Icon name="refresh" size={14} /> Refresh</button>
          ) : null}
        </div>
        {usageProvider && usage.data ? (
          <>
            <div className="stat-grid compact-stats">
              <div className="stat-cell"><span>Calls</span><strong>{formatNumber(usage.data.totals.calls)}</strong></div>
              <div className="stat-cell"><span>Input tokens</span><strong>{formatNumber(usage.data.totals.input_tokens)}</strong></div>
              <div className="stat-cell"><span>Output tokens</span><strong>{formatNumber(usage.data.totals.output_tokens)}</strong></div>
              <div className="stat-cell"><span>Recorded cost</span><strong>${usage.data.totals.cost.toFixed(6)}</strong></div>
            </div>
            {usage.data.items.length ? (
              <div className="table-wrap">
                <table className="data-table usage-table">
                  <thead><tr><th>Time</th><th>Model</th><th>Status</th><th>Tokens</th><th>Latency</th><th>Cost</th><th>Detail</th></tr></thead>
                  <tbody>
                    {usage.data.items.map((row) => (
                      <tr key={row.id}>
                        <td className="muted">{formatDateTime(row.created_at)}</td>
                        <td className="mono">{row.model}</td>
                        <td><StatusBadge status={row.status} /></td>
                        <td>{row.input_tokens} / {row.output_tokens}</td>
                        <td>{Math.round(row.latency_ms)} ms</td>
                        <td>${row.cost.toFixed(6)}</td>
                        <td className="error-cell">{row.error ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">No usage recorded for this provider yet.</p>
            )}
          </>
        ) : (
          <p className="muted">Choose a provider to view its usage history.</p>
        )}
      </Card>

      <Modal
        open={testTarget !== null}
        title={`Test ${testTarget?.name ?? 'provider'}?`}
        subtitle="This is an explicit connection test, not a background check."
        onClose={() => setTestTarget(null)}
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => setTestTarget(null)}>Cancel</button>
            <button type="button" className="btn btn-primary" onClick={() => testTarget && void test(testTarget)} disabled={busy !== null}>
              {busy ? 'Testing…' : 'Run connection test'}
            </button>
          </>
        }
      >
        {testTarget ? (
          <div className="stack-sm">
            <p>A test sends a minimal request to <strong>{testTarget.name}</strong> using model <code className="inline-code">{testTarget.default_model}</code>.</p>
            {testTarget.external ? (
              <InlineNotice tone="warn" title="External network call" icon="alert">
                This will contact {testTarget.base_url} and may incur a small provider charge. External calls must be enabled in Settings. The credential is read from encrypted storage or the {testTarget.api_key_env} environment variable and is never displayed.
              </InlineNotice>
            ) : (
              <InlineNotice tone="info" title="Offline test" icon="flask">The mock provider performs no network I/O.</InlineNotice>
            )}
          </div>
        ) : null}
      </Modal>

      <Modal
        open={keyTarget !== null}
        title={`Store credential for ${keyTarget?.name ?? 'provider'}`}
        subtitle="Encrypted on this machine. It cannot be retrieved or displayed."
        onClose={() => { setKeyTarget(null); setKeyDraft(''); }}
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => { setKeyTarget(null); setKeyDraft(''); }}>Cancel</button>
            <button type="button" className="btn btn-primary" onClick={() => void saveKey()} disabled={busy !== null || !keyDraft.trim()}>
              {busy ? 'Storing…' : 'Store credential'}
            </button>
          </>
        }
      >
        <div className="stack-sm">
          <p>
            The key is protected with <strong>{credentials.data?.backend ?? 'the local credential store'}</strong>.
            It is used only for outbound provider requests and is excluded from exports, logs, and the API.
          </p>
          <label className="field">
            <span className="field-label">API key</span>
            <input
              className="input"
              type="password"
              value={keyDraft}
              onChange={(event) => setKeyDraft(event.target.value)}
              placeholder="Paste the provider API key"
              autoComplete="off"
              onKeyDown={(event) => { if (event.key === 'Enter' && keyDraft.trim()) void saveKey(); }}
            />
          </label>
          <InlineNotice tone="warn" title="Confirm before storing" icon="key">
            Storing replaces any existing credential for this provider. Clear it at any time from the provider card.
          </InlineNotice>
        </div>
      </Modal>
    </>
  );
}

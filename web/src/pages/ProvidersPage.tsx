import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatNumber, relativeTime, titleCase } from '../lib/format';
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
  };
}

export function ProvidersPage() {
  const { notify } = useToast();
  const providers = useApi(() => api.providers.list(), []);
  const settings = useApi(() => api.settings.get(), []);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testTarget, setTestTarget] = useState<Provider | null>(null);
  const [testResults, setTestResults] = useState<Record<string, Record<string, unknown>>>({});

  function startEdit(provider: Provider) {
    setEditing(provider.id);
    setDraft(draftFrom(provider));
    setError(null);
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
        models: draft.models
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        input_cost_per_1k: Number(draft.input_cost_per_1k),
        output_cost_per_1k: Number(draft.output_cost_per_1k),
        max_output_tokens: Number(draft.max_output_tokens),
        timeout_seconds: Number(draft.timeout_seconds),
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

  const externalEnabled = settings.data?.allow_external_calls ?? false;

  return (
    <>
      <PageHeader
        eyebrow="Control"
        title="Providers"
        description="Real provider adapters with explicit opt-in. API keys stay in environment variables and are never stored, logged, or returned."
        actions={
          <Link to="/app/settings" className="btn btn-outline btn-sm">
            <Icon name="settings" size={15} /> Call policy
          </Link>
        }
      />

      {providers.error ? <ErrorState message={providers.error} onRetry={providers.reload} /> : null}
      {providers.loading && !providers.data ? <LoadingBlock label="Loading providers…" /> : null}

      {providers.data && !externalEnabled ? (
        <InlineNotice tone="info" title="External calls are disabled" icon="lock">
          The offline mock provider works without configuration. Gemini and OpenAI-compatible
          adapters exist, but execution and connection tests are blocked until external calls are
          explicitly enabled in <Link to="/app/settings">Settings</Link>.
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
                  <span className="field-label">Key present</span>
                  <span>{provider.external ? (provider.key_present ? 'Yes' : 'No') : 'N/A'}</span>
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
                  <span className="field-label">Pricing configured</span>
                  <span>
                    {provider.cost_configured
                      ? `$${provider.input_cost_per_1k}/1k in · $${provider.output_cost_per_1k}/1k out`
                      : 'Not configured (cost recorded as $0)'}
                  </span>
                </div>
                <div>
                  <span className="field-label">Max output tokens</span>
                  <span>{formatNumber(provider.max_output_tokens)}</span>
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
                      <input
                        className="input"
                        value={draft.name}
                        onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                      />
                    </label>
                    <label className="checkbox-field provider-enabled">
                      <input
                        type="checkbox"
                        checked={draft.enabled}
                        onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
                      />
                      <span>Enabled for routing</span>
                    </label>
                    <label className="field span-2">
                      <span className="field-label">Base URL</span>
                      <input
                        className="input"
                        value={draft.base_url}
                        onChange={(event) => setDraft({ ...draft, base_url: event.target.value })}
                        placeholder="https://…"
                      />
                      <span className="field-hint">HTTPS is required except for localhost endpoints.</span>
                    </label>
                    <label className="field">
                      <span className="field-label">API key environment variable</span>
                      <input
                        className="input"
                        value={draft.api_key_env}
                        onChange={(event) => setDraft({ ...draft, api_key_env: event.target.value })}
                        placeholder="GEMINI_API_KEY"
                      />
                      <span className="field-hint">The value is read from the process environment only.</span>
                    </label>
                    <label className="field">
                      <span className="field-label">Default model</span>
                      <input
                        className="input"
                        value={draft.default_model}
                        onChange={(event) => setDraft({ ...draft, default_model: event.target.value })}
                      />
                    </label>
                    <label className="field span-2">
                      <span className="field-label">Models (comma separated)</span>
                      <input
                        className="input"
                        value={draft.models}
                        onChange={(event) => setDraft({ ...draft, models: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span className="field-label">Input cost per 1k tokens (USD)</span>
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="0.000001"
                        value={draft.input_cost_per_1k}
                        onChange={(event) =>
                          setDraft({ ...draft, input_cost_per_1k: event.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span className="field-label">Output cost per 1k tokens (USD)</span>
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="0.000001"
                        value={draft.output_cost_per_1k}
                        onChange={(event) =>
                          setDraft({ ...draft, output_cost_per_1k: event.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span className="field-label">Max output tokens</span>
                      <input
                        className="input"
                        type="number"
                        min="1"
                        value={draft.max_output_tokens}
                        onChange={(event) =>
                          setDraft({ ...draft, max_output_tokens: event.target.value })
                        }
                      />
                    </label>
                    <label className="field">
                      <span className="field-label">Timeout (seconds)</span>
                      <input
                        className="input"
                        type="number"
                        min="1"
                        max="600"
                        value={draft.timeout_seconds}
                        onChange={(event) =>
                          setDraft({ ...draft, timeout_seconds: event.target.value })
                        }
                      />
                    </label>
                  </div>
                  <div className="provider-form-actions">
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => {
                        setEditing(null);
                        setDraft(null);
                      }}
                      disabled={busy === `save-${provider.id}`}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => void save(provider)}
                      disabled={busy === `save-${provider.id}`}
                    >
                      {busy === `save-${provider.id}` ? 'Saving…' : 'Save provider'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="provider-actions">
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => startEdit(provider)}
                  >
                    <Icon name="edit" size={15} /> Configure
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => setTestTarget(provider)}
                    disabled={busy === `test-${provider.id}`}
                  >
                    <Icon name="spark" size={15} /> Test connection
                  </button>
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Modal
        open={testTarget !== null}
        title={`Test ${testTarget?.name ?? 'provider'}?`}
        subtitle="This is an explicit connection test, not a background check."
        onClose={() => setTestTarget(null)}
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => setTestTarget(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => testTarget && void test(testTarget)}
              disabled={busy !== null}
            >
              {busy ? 'Testing…' : 'Run connection test'}
            </button>
          </>
        }
      >
        {testTarget ? (
          <div className="stack-sm">
            <p>
              A test sends a minimal request to <strong>{testTarget.name}</strong> using model{' '}
              <code className="inline-code">{testTarget.default_model}</code>.
            </p>
            {testTarget.external ? (
              <InlineNotice tone="warn" title="External network call" icon="alert">
                This will contact {testTarget.base_url} and may incur a small provider charge. External
                calls must be enabled in Settings. The API key is read from{' '}
                <code className="inline-code">{testTarget.api_key_env}</code> and is never displayed.
              </InlineNotice>
            ) : (
              <InlineNotice tone="info" title="Offline test" icon="flask">
                The mock provider performs no network I/O.
              </InlineNotice>
            )}
          </div>
        ) : null}
      </Modal>
    </>
  );
}

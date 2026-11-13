import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, getToken, setToken } from '../lib/api';
import { formatBytes, formatDateTime, formatNumber } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { Settings } from '../lib/types';
import { Icon } from '../components/Icons';
import { ConfirmDialog } from '../components/Modal';
import {
  Badge,
  Card,
  ErrorState,
  InlineNotice,
  LoadingBlock,
  PageHeader,
} from '../components/UI';

export function SettingsPage() {
  const { notify } = useToast();
  const settingsState = useApi(() => api.settings.get(), []);
  const providers = useApi(() => api.providers.list(), []);
  const diagnostics = useApi(() => api.diagnostics(), []);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [externalConfirm, setExternalConfirm] = useState(false);
  const [purgeConfirm, setPurgeConfirm] = useState(false);
  const [tokenDraft, setTokenDraft] = useState(getToken());

  useEffect(() => {
    if (settingsState.data) setDraft(settingsState.data);
  }, [settingsState.data]);

  function setField<K extends keyof Settings>(key: K, value: Settings[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  function updateMaxAutonomy(value: number) {
    setDraft((current) =>
      current
        ? {
            ...current,
            max_autonomy_level: value,
            default_autonomy_level: Math.min(current.default_autonomy_level, value),
          }
        : current,
    );
  }

  function updateMaxBudget(value: number) {
    setDraft((current) =>
      current
        ? {
            ...current,
            max_task_budget: value,
            default_budget: Math.min(current.default_budget, value),
          }
        : current,
    );
  }

  function updateMaxTokens(value: number) {
    setDraft((current) =>
      current
        ? {
            ...current,
            max_token_budget: value,
            default_token_budget: Math.min(current.default_token_budget, value),
          }
        : current,
    );
  }

  function updateMaxSeconds(value: number) {
    setDraft((current) =>
      current
        ? {
            ...current,
            max_execution_seconds: value,
            default_timeout_seconds: Math.min(current.default_timeout_seconds, value),
          }
        : current,
    );
  }

  async function save() {
    if (!draft) return;
    setBusy('save');
    setError(null);
    try {
      const updated = await api.settings.update(draft);
      setDraft(updated);
      notify('Settings saved.', 'success');
      settingsState.reload();
      diagnostics.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function exportBackup() {
    setBusy('export');
    setError(null);
    try {
      await api.exportBackup();
      notify('Backup downloaded. Provider credentials are not included.', 'success');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  async function purge() {
    setBusy('purge');
    setError(null);
    try {
      const result = await api.purge(true, true);
      notify(`Purged ${result.purged} soft-deleted task(s).`, 'success');
      setPurgeConfirm(false);
      diagnostics.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function saveApiToken() {
    setToken(tokenDraft.trim());
    notify(
      tokenDraft.trim()
        ? 'API token stored in this browser only.'
        : 'Stored API token cleared from this browser.',
      'success',
    );
  }

  const providerList = providers.data ?? [];
  const defaultProvider = providerList.find((provider) => provider.id === draft?.default_provider);
  const verifierProvider = providerList.find((provider) => provider.id === draft?.verifier_provider);
  const loading = settingsState.loading || providers.loading;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Settings"
        description="Defaults, ceilings, safety switches, verification mode, retention, and local access. All limits are enforced server-side."
        actions={
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => void save()}
            disabled={!draft || busy !== null}
          >
            {busy === 'save' ? 'Saving…' : 'Save settings'}
          </button>
        }
      />

      {settingsState.error ? <ErrorState message={settingsState.error} onRetry={settingsState.reload} /> : null}
      {providers.error ? <ErrorState message={providers.error} onRetry={providers.reload} /> : null}
      {loading && !draft ? <LoadingBlock label="Loading settings…" /> : null}

      {error ? (
        <InlineNotice tone="danger" title="Settings were not saved" icon="alert">
          {error}
        </InlineNotice>
      ) : null}

      {draft ? (
        <div className="settings-stack">
          <Card title="Defaults" subtitle="Applied when a task does not specify its own value">
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Default autonomy level</span>
                <select
                  className="select"
                  value={draft.default_autonomy_level}
                  onChange={(event) => setField('default_autonomy_level', Number(event.target.value))}
                >
                  {Array.from({ length: draft.max_autonomy_level }, (_, index) => index + 1).map(
                    (level) => (
                      <option key={level} value={level}>
                        Level {level}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Default risk class</span>
                <select
                  className="select"
                  value={draft.default_risk_class}
                  onChange={(event) =>
                    setField('default_risk_class', event.target.value as Settings['default_risk_class'])
                  }
                >
                  <option value="low">Low</option>
                  <option value="med">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label className="field">
                <span className="field-label">Default cost budget (USD)</span>
                <input
                  className="input"
                  type="number"
                  min="0.000001"
                  step="any"
                  value={draft.default_budget}
                  onChange={(event) => setField('default_budget', Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span className="field-label">Default token budget</span>
                <input
                  className="input"
                  type="number"
                  min="1"
                  value={draft.default_token_budget}
                  onChange={(event) => setField('default_token_budget', Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span className="field-label">Default timeout (seconds)</span>
                <input
                  className="input"
                  type="number"
                  min="1"
                  value={draft.default_timeout_seconds}
                  onChange={(event) =>
                    setField('default_timeout_seconds', Number(event.target.value))
                  }
                />
              </label>
              <label className="field">
                <span className="field-label">Default provider</span>
                <select
                  className="select"
                  value={draft.default_provider}
                  onChange={(event) => {
                    const provider = providerList.find((entry) => entry.id === event.target.value);
                    setDraft((current) =>
                      current
                        ? {
                            ...current,
                            default_provider: event.target.value,
                            default_model:
                              provider?.default_model ?? provider?.models[0] ?? current.default_model,
                          }
                        : current,
                    );
                  }}
                >
                  {providerList.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Default model</span>
                <select
                  className="select"
                  value={draft.default_model}
                  onChange={(event) => setField('default_model', event.target.value)}
                >
                  {(defaultProvider?.models ?? [draft.default_model]).map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </Card>

          <Card title="Global ceilings" subtitle="Tasks cannot exceed these values">
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Maximum autonomy level</span>
                <select
                  className="select"
                  value={draft.max_autonomy_level}
                  onChange={(event) => updateMaxAutonomy(Number(event.target.value))}
                >
                  {[1, 2, 3, 4, 5].map((level) => (
                    <option key={level} value={level}>
                      Level {level}
                    </option>
                  ))}
                </select>
                <span className="field-hint">
                  Levels 4–5 enable adaptation or custom policies. Level 3 is the default posture.
                </span>
              </label>
              <label className="field">
                <span className="field-label">Maximum task budget (USD)</span>
                <input
                  className="input"
                  type="number"
                  min="0.000001"
                  step="any"
                  value={draft.max_task_budget}
                  onChange={(event) => updateMaxBudget(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span className="field-label">Maximum token budget</span>
                <input
                  className="input"
                  type="number"
                  min="1"
                  value={draft.max_token_budget}
                  onChange={(event) => updateMaxTokens(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span className="field-label">Maximum execution time (seconds)</span>
                <input
                  className="input"
                  type="number"
                  min="1"
                  value={draft.max_execution_seconds}
                  onChange={(event) => updateMaxSeconds(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span className="field-label">Recovery attempts</span>
                <select
                  className="select"
                  value={draft.max_recovery_attempts}
                  onChange={(event) => setField('max_recovery_attempts', Number(event.target.value))}
                >
                  <option value={0}>No automatic recovery</option>
                  <option value={1}>1 retry</option>
                  <option value={2}>2 retries</option>
                  <option value={3}>3 retries</option>
                </select>
                <span className="field-hint">
                  Recovery runs only at autonomy level 3 or above and remains inside the same budget.
                </span>
              </label>
            </div>
          </Card>

          <Card title="Safety and approvals" subtitle="These switches cannot be bypassed by a task">
            <div className="switch-list">
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.allow_external_calls}
                  onChange={(event) => {
                    if (event.target.checked) setExternalConfirm(true);
                    else setField('allow_external_calls', false);
                  }}
                />
                <span>
                  <strong>Allow external provider calls</strong>
                  <small>
                    Enables network requests to Gemini or an OpenAI-compatible endpoint. Off by
                    default. Enabling this does not spend money until a task or explicit connection
                    test runs.
                  </small>
                </span>
                <Badge tone={draft.allow_external_calls ? 'warn' : 'success'}>
                  {draft.allow_external_calls ? 'Enabled' : 'Disabled'}
                </Badge>
              </label>
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.require_approval_high_risk}
                  onChange={(event) => setField('require_approval_high_risk', event.target.checked)}
                />
                <span>
                  <strong>Require approval for high-risk tasks</strong>
                  <small>High-risk provider calls pause for a fresh human decision.</small>
                </span>
                <Badge tone={draft.require_approval_high_risk ? 'success' : 'danger'}>
                  {draft.require_approval_high_risk ? 'On' : 'Off'}
                </Badge>
              </label>
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.require_approval_external}
                  onChange={(event) => setField('require_approval_external', event.target.checked)}
                />
                <span>
                  <strong>Require approval for external providers</strong>
                  <small>External calls pause for approval even when external calls are enabled.</small>
                </span>
                <Badge tone={draft.require_approval_external ? 'success' : 'warn'}>
                  {draft.require_approval_external ? 'On' : 'Off'}
                </Badge>
              </label>
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.allow_custom_policies}
                  onChange={(event) => setField('allow_custom_policies', event.target.checked)}
                />
                <span>
                  <strong>Allow custom task policies</strong>
                  <small>
                    Only used at autonomy level 5. Custom policies can narrow actions, providers,
                    models, risk classes, budgets, and timeouts.
                  </small>
                </span>
                <Badge tone={draft.allow_custom_policies ? 'success' : 'neutral'}>
                  {draft.allow_custom_policies ? 'On' : 'Off'}
                </Badge>
              </label>
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.routing_fallback_enabled}
                  onChange={(event) => setField('routing_fallback_enabled', event.target.checked)}
                />
                <span>
                  <strong>Enable routing fallback</strong>
                  <small>
                    Try the next routing candidate when one is unavailable. Off means routing fails
                    closed on the first invalid candidate.
                  </small>
                </span>
                <Badge tone={draft.routing_fallback_enabled ? 'info' : 'neutral'}>
                  {draft.routing_fallback_enabled ? 'On' : 'Off'}
                </Badge>
              </label>
            </div>
          </Card>

          <Card title="Verification" subtitle="Deterministic by default; provider verification is optional">
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Verification mode</span>
                <select
                  className="select"
                  value={draft.verification_mode}
                  onChange={(event) =>
                    setField('verification_mode', event.target.value as Settings['verification_mode'])
                  }
                >
                  <option value="deterministic">Deterministic checks only</option>
                  <option value="provider">Deterministic + provider verifier</option>
                </select>
                <span className="field-hint">
                  A verifier only counts as independent when it uses a different provider or model
                  from the generator.
                </span>
              </label>
              {draft.verification_mode === 'provider' ? (
                <>
                  <label className="field">
                    <span className="field-label">Verifier provider</span>
                    <select
                      className="select"
                      value={draft.verifier_provider}
                      onChange={(event) => {
                        const provider = providerList.find((entry) => entry.id === event.target.value);
                        setDraft((current) =>
                          current
                            ? {
                                ...current,
                                verifier_provider: event.target.value,
                                verifier_model:
                                  provider?.default_model ??
                                  provider?.models[0] ??
                                  current.verifier_model,
                              }
                            : current,
                        );
                      }}
                    >
                      <option value="">Select a provider</option>
                      {providerList.map((provider) => (
                        <option key={provider.id} value={provider.id}>
                          {provider.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field-label">Verifier model</span>
                    <select
                      className="select"
                      value={draft.verifier_model}
                      onChange={(event) => setField('verifier_model', event.target.value)}
                    >
                      {(verifierProvider?.models ?? [draft.verifier_model]).map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : null}
            </div>
            <InlineNotice tone="info" title="Independence is recorded honestly" icon="info">
              The offline mock verifier is never counted as independent evidence. With only mock
              evidence, high-risk tasks correctly abstain at the gate.
            </InlineNotice>
          </Card>

          <Card title="Retention" subtitle="Soft-deleted task history">
            <div className="switch-list">
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={draft.retention_enabled}
                  onChange={(event) => setField('retention_enabled', event.target.checked)}
                />
                <span>
                  <strong>Enable retention cleanup</strong>
                  <small>
                    Allows purging soft-deleted tasks older than the retention window. Purge remains
                    an explicit, confirmed action.
                  </small>
                </span>
                <Badge tone={draft.retention_enabled ? 'success' : 'neutral'}>
                  {draft.retention_enabled ? 'On' : 'Off'}
                </Badge>
              </label>
            </div>
            <label className="field retention-days">
              <span className="field-label">Retention window (days)</span>
              <input
                className="input"
                type="number"
                min="1"
                max="3650"
                value={draft.retention_days}
                onChange={(event) => setField('retention_days', Number(event.target.value))}
              />
            </label>
          </Card>

          <Card title="Local API access" subtitle="Optional bearer token for the local API">
            <p className="muted">
              If the server starts with the <code className="inline-code">CREST_API_TOKEN</code>{' '}
              environment variable, every API route except health requires a bearer token. Store the
              same token in this browser; it is kept in localStorage and never sent anywhere else.
            </p>
            <div className="token-row">
              <input
                className="input"
                type="password"
                value={tokenDraft}
                onChange={(event) => setTokenDraft(event.target.value)}
                placeholder="Paste the token configured on the server"
                autoComplete="off"
              />
              <button type="button" className="btn btn-outline" onClick={saveApiToken}>
                Save token
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setTokenDraft('');
                  setToken('');
                  notify('Stored API token cleared from this browser.', 'info');
                }}
              >
                Clear
              </button>
            </div>
            <p className="muted small">
              Server status: {diagnostics.data?.auth_token_required ? 'token required' : 'token not required'}.
            </p>
          </Card>

          <Card title="Data management" subtitle="Backups and confirmed cleanup">
            <div className="data-grid">
              <div className="data-block">
                <h3>Export backup</h3>
                <p className="muted">
                  Download tasks, plans, executions, evidence, approvals, audit events, routing, and
                  settings. Provider credentials are excluded.
                </p>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => void exportBackup()}
                  disabled={busy !== null}
                >
                  <Icon name="download" size={15} /> Download JSON backup
                </button>
              </div>
              <div className="data-block">
                <h3>Database</h3>
                <dl className="meta-list compact">
                  <div className="meta-row">
                    <dt>Path</dt>
                    <dd className="mono wrap-anywhere">{diagnostics.data?.database.path ?? '—'}</dd>
                  </div>
                  <div className="meta-row">
                    <dt>Size</dt>
                    <dd>{formatBytes(diagnostics.data?.database.size_bytes)}</dd>
                  </div>
                  <div className="meta-row">
                    <dt>Integrity</dt>
                    <dd>
                      {diagnostics.data?.database.integrity.ok ? (
                        <Badge tone="success">OK</Badge>
                      ) : (
                        <Badge tone="danger">Check failed</Badge>
                      )}
                    </dd>
                  </div>
                  <div className="meta-row">
                    <dt>Tasks</dt>
                    <dd>{formatNumber(diagnostics.data?.database.counts.tasks ?? 0)}</dd>
                  </div>
                  <div className="meta-row">
                    <dt>Started</dt>
                    <dd>{formatDateTime(diagnostics.data?.started_at)}</dd>
                  </div>
                </dl>
              </div>
            </div>
            <div className="danger-zone">
              <div>
                <h3>Purge soft-deleted tasks</h3>
                <p className="muted">
                  Permanently removes soft-deleted tasks older than {draft.retention_days} days. Audit
                  events are retained. This cannot be undone.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => setPurgeConfirm(true)}
                disabled={busy !== null}
              >
                <Icon name="trash" size={15} /> Purge…
              </button>
            </div>
          </Card>

          <div className="settings-footer">
            <Link to="/app/system" className="btn btn-outline btn-sm">
              <Icon name="system" size={15} /> System diagnostics
            </Link>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void save()}
              disabled={busy !== null}
            >
              {busy === 'save' ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={externalConfirm}
        title="Enable external provider calls?"
        description="This allows CREST to make network requests to configured external providers. Requests can incur charges. External calls still require a configured key, an enabled provider, and approval when that safety switch is on."
        confirmLabel="Enable in form"
        onConfirm={() => {
          setField('allow_external_calls', true);
          setExternalConfirm(false);
          notify('External calls enabled in the form. Save settings to apply.', 'info');
        }}
        onClose={() => setExternalConfirm(false)}
      />

      <ConfirmDialog
        open={purgeConfirm}
        title="Permanently purge deleted tasks?"
        description="This removes soft-deleted task records and their executions and evidence. Audit events remain. This action cannot be undone."
        confirmLabel="Purge permanently"
        danger
        busy={busy === 'purge'}
        onConfirm={() => void purge()}
        onClose={() => setPurgeConfirm(false)}
      />
    </>
  );
}

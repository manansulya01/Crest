import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { RoutingRule } from '../lib/types';
import { Icon } from '../components/Icons';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingBlock,
  PageHeader,
} from '../components/UI';

export function RoutingPage() {
  const { notify } = useToast();
  const routing = useApi(() => api.routing.get(), []);
  const providers = useApi(() => api.providers.list(), []);
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [fallback, setFallback] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!routing.data) return;
    setRules(routing.data.rules.map((rule) => ({ ...rule })));
    setFallback(routing.data.fallback_enabled);
  }, [routing.data]);

  const providerList = providers.data ?? [];

  function updateRule(index: number, patch: Partial<RoutingRule>) {
    setRules((current) =>
      current.map((rule, position) => (position === index ? { ...rule, ...patch } : rule)),
    );
  }

  function addRule() {
    const first = providerList[0];
    setRules((current) => [
      ...current,
      {
        priority: (current.at(-1)?.priority ?? 90) + 10,
        risk_class: '*',
        provider: first?.id ?? 'mock',
        model: first?.default_model ?? first?.models[0] ?? 'mock-fast',
        enabled: true,
      },
    ]);
  }

  function selectProvider(index: number, providerId: string) {
    const provider = providerList.find((entry) => entry.id === providerId);
    updateRule(index, {
      provider: providerId,
      model: provider?.default_model ?? provider?.models[0] ?? '',
    });
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.routing.update(rules, fallback);
      notify('Routing rules saved.', 'success');
      routing.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Control"
        title="Model routing"
        description="Deterministic routing by risk class and priority. A task-level provider/model selection is considered first; application defaults are the last resort."
        actions={
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => void save()}
            disabled={busy || rules.length === 0}
          >
            {busy ? 'Saving…' : 'Save routing'}
          </button>
        }
      />

      {routing.error ? <ErrorState message={routing.error} onRetry={routing.reload} /> : null}
      {providers.error ? <ErrorState message={providers.error} onRetry={providers.reload} /> : null}
      {routing.loading && !routing.data ? <LoadingBlock label="Loading routing rules…" /> : null}

      {error ? (
        <InlineNotice tone="danger" title="Routing could not be saved" icon="alert">
          {error}
        </InlineNotice>
      ) : null}

      {routing.data ? (
        <>
          <InlineNotice tone="info" title="Resolution order" icon="route">
            Task override → enabled routing rules in ascending priority → application default. Fallback
            to the next candidate is only attempted when fallback is enabled; otherwise routing fails
            closed.
          </InlineNotice>

          <Card
            title="Routing rules"
            subtitle="Lower priority numbers are evaluated first"
            actions={
              <button type="button" className="btn btn-outline btn-sm" onClick={addRule}>
                <Icon name="plus" size={15} /> Add rule
              </button>
            }
            padded={false}
          >
            {rules.length === 0 ? (
              <div className="card-body">
                <EmptyState
                  icon="route"
                  title="No routing rules"
                  description="Add at least one rule, or restore a rule that points to an enabled provider."
                  action={
                    <button type="button" className="btn btn-primary btn-sm" onClick={addRule}>
                      Add a rule
                    </button>
                  }
                />
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table routing-table">
                  <thead>
                    <tr>
                      <th>Priority</th>
                      <th>Risk class</th>
                      <th>Provider</th>
                      <th>Model</th>
                      <th>Enabled</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((rule, index) => {
                      const provider = providerList.find((entry) => entry.id === rule.provider);
                      return (
                        <tr key={index}>
                          <td>
                            <input
                              className="input input-sm input-number"
                              type="number"
                              value={rule.priority}
                              onChange={(event) =>
                                updateRule(index, { priority: Number(event.target.value) })
                              }
                            />
                          </td>
                          <td>
                            <select
                              className="select select-sm"
                              value={rule.risk_class}
                              onChange={(event) =>
                                updateRule(index, {
                                  risk_class: event.target.value as RoutingRule['risk_class'],
                                })
                              }
                            >
                              <option value="*">Any</option>
                              <option value="high">High</option>
                              <option value="med">Medium</option>
                              <option value="low">Low</option>
                            </select>
                          </td>
                          <td>
                            <select
                              className="select select-sm"
                              value={rule.provider}
                              onChange={(event) => selectProvider(index, event.target.value)}
                            >
                              {providerList.map((entry) => (
                                <option key={entry.id} value={entry.id}>
                                  {entry.name}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <select
                              className="select select-sm"
                              value={rule.model}
                              onChange={(event) => updateRule(index, { model: event.target.value })}
                            >
                              {(provider?.models ?? [rule.model]).map((model) => (
                                <option key={model} value={model}>
                                  {model}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <label className="checkbox-field checkbox-compact">
                              <input
                                type="checkbox"
                                checked={rule.enabled}
                                onChange={(event) =>
                                  updateRule(index, { enabled: event.target.checked })
                                }
                              />
                              <span>{rule.enabled ? 'On' : 'Off'}</span>
                            </label>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-icon btn-ghost btn-danger-text"
                              aria-label="Remove routing rule"
                              onClick={() =>
                                setRules((current) =>
                                  current.filter((_, position) => position !== index),
                                )
                              }
                            >
                              <Icon name="trash" size={15} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="two-col">
            <Card title="Fallback behavior">
              <label className="switch-row">
                <input
                  type="checkbox"
                  checked={fallback}
                  onChange={(event) => setFallback(event.target.checked)}
                />
                <span>
                  <strong>Enable routing fallback</strong>
                  <small>
                    When a candidate provider is disabled, missing a key, or missing the model, try the
                    next candidate. When disabled, routing fails closed on the first invalid candidate.
                  </small>
                </span>
              </label>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => void save()}
                disabled={busy}
              >
                Save fallback setting
              </button>
            </Card>

            <Card title="Provider availability">
              {providerList.length === 0 ? (
                <EmptyState icon="providers" title="No providers configured" />
              ) : (
                <ul className="provider-status-list">
                  {providerList.map((provider) => (
                    <li key={provider.id}>
                      <div>
                        <strong>{provider.name}</strong>
                        <small>
                          {provider.models.join(', ') || 'No models'} ·{' '}
                          {provider.external ? 'external' : 'offline'}
                        </small>
                      </div>
                      <div className="provider-status-badges">
                        <Badge tone={provider.enabled ? 'success' : 'neutral'}>
                          {provider.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                        <Badge tone={provider.status === 'ready' ? 'success' : 'warn'}>
                          {titleCase(provider.status)}
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/app/providers" className="btn btn-outline btn-sm btn-block">
                Configure providers
              </Link>
            </Card>
          </div>
        </>
      ) : null}
    </>
  );
}

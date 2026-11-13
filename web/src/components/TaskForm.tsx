import { useState } from 'react';
import type { FormEvent } from 'react';
import { Icon } from './Icons';
import { InlineNotice } from './UI';
import type { Provider, Settings, Task, TaskPayload } from '../lib/types';

const LEVEL_NAMES: Record<number, string> = {
  1: 'Observe',
  2: 'Assisted',
  3: 'Bounded',
  4: 'Adaptive',
  5: 'Custom',
};

const DEMO_LABELS: Record<string, string> = {
  verification_failure: 'Verification failure (mock)',
  recovery: 'Recovery retry (mock)',
  approval_required: 'Approval required (mock)',
};

const DEFAULT_CUSTOM_POLICY = `{
  "allowed_actions": ["plan", "provider_call", "verify", "recover"],
  "allowed_risk_classes": ["low", "med"],
  "require_approval": false,
  "max_cost": 1.0
}`;

interface Props {
  mode: 'create' | 'edit';
  initial?: Task;
  settings: Settings;
  providers: Provider[];
  busy: boolean;
  submitLabel: string;
  allowExecuteNow?: boolean;
  onCancel?: () => void;
  onSubmit: (payload: TaskPayload, executeNow: boolean) => void | Promise<void>;
}

export function TaskForm({
  mode,
  initial,
  settings,
  providers,
  busy,
  submitLabel,
  allowExecuteNow = false,
  onCancel,
  onSubmit,
}: Props) {
  const initialProvider =
    initial?.provider ?? settings.default_provider ?? providers[0]?.id ?? 'mock';
  const initialProviderRow = providers.find((provider) => provider.id === initialProvider);
  const initialModel =
    initial?.model ??
    initialProviderRow?.default_model ??
    initialProviderRow?.models[0] ??
    settings.default_model ??
    '';

  const [title, setTitle] = useState(initial?.title ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [risk, setRisk] = useState(initial?.risk_class ?? settings.default_risk_class);
  const [autonomy, setAutonomy] = useState(
    Math.min(initial?.autonomy_level ?? settings.default_autonomy_level, settings.max_autonomy_level),
  );
  const [providerId, setProviderId] = useState(initialProvider);
  const [model, setModel] = useState(initialModel);
  const [budget, setBudget] = useState(String(initial?.budget ?? settings.default_budget));
  const [tokenBudget, setTokenBudget] = useState(
    String(initial?.token_budget ?? settings.default_token_budget),
  );
  const [timeoutSeconds, setTimeoutSeconds] = useState(
    String(initial?.timeout_seconds ?? settings.default_timeout_seconds),
  );
  const [criteria, setCriteria] = useState<string[]>(
    initial?.acceptance_criteria?.length ? initial.acceptance_criteria : [''],
  );
  const [outputFormat, setOutputFormat] = useState<'text' | 'json'>(
    initial?.output_format ?? 'text',
  );
  const [demoScenario, setDemoScenario] = useState(initial?.demo_scenario ?? '');
  const [customPolicy, setCustomPolicy] = useState(
    initial?.custom_policy ? JSON.stringify(initial.custom_policy, null, 2) : DEFAULT_CUSTOM_POLICY,
  );
  const [executeNow, setExecuteNow] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);

  const provider = providers.find((entry) => entry.id === providerId);
  const isMock = provider?.kind === 'mock';
  const externalBlocked = Boolean(provider?.external && !settings.allow_external_calls);

  function selectProvider(nextId: string) {
    setProviderId(nextId);
    const next = providers.find((entry) => entry.id === nextId);
    setModel(next?.default_model ?? next?.models[0] ?? '');
    if (next?.kind !== 'mock') setDemoScenario('');
  }

  function updateCriterion(index: number, value: string) {
    setCriteria((current) => current.map((item, position) => (position === index ? value : item)));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);

    if (!title.trim()) {
      setLocalError('A task title is required.');
      return;
    }
    const parsedBudget = Number(budget);
    const parsedTokens = Number(tokenBudget);
    const parsedTimeout = Number(timeoutSeconds);
    if (!Number.isFinite(parsedBudget) || parsedBudget <= 0) {
      setLocalError('Budget must be a positive number.');
      return;
    }
    if (!Number.isFinite(parsedTokens) || !Number.isInteger(parsedTokens) || parsedTokens <= 0) {
      setLocalError('Token budget must be a positive whole number.');
      return;
    }
    if (!Number.isFinite(parsedTimeout) || parsedTimeout <= 0) {
      setLocalError('Timeout must be a positive number of seconds.');
      return;
    }

    let parsedPolicy: Record<string, unknown> | null = null;
    if (autonomy === 5) {
      try {
        const candidate = JSON.parse(customPolicy) as unknown;
        if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
          throw new Error('custom policy must be a JSON object');
        }
        parsedPolicy = candidate as Record<string, unknown>;
      } catch (caught) {
        setLocalError(
          `Custom policy is not valid JSON: ${caught instanceof Error ? caught.message : String(caught)}`,
        );
        return;
      }
    }

    const payload: TaskPayload = {
      title: title.trim(),
      description: description.trim(),
      risk_class: risk,
      autonomy_level: autonomy,
      provider: providerId,
      model,
      budget: parsedBudget,
      token_budget: parsedTokens,
      timeout_seconds: parsedTimeout,
      acceptance_criteria: criteria.map((item) => item.trim()).filter(Boolean),
      output_format: outputFormat,
      demo_scenario: demoScenario ? (demoScenario as TaskPayload['demo_scenario']) : null,
      custom_policy: autonomy === 5 ? parsedPolicy : null,
    };
    void onSubmit(payload, allowExecuteNow && executeNow);
  }

  return (
    <form className="task-form" onSubmit={handleSubmit}>
      {localError ? (
        <InlineNotice tone="danger" title="Check the form" icon="alert">
          {localError}
        </InlineNotice>
      ) : null}
      {externalBlocked ? (
        <InlineNotice tone="warn" title="External provider selected" icon="alert">
          External calls are disabled in Settings, so this task will be denied at execution. Enable
          external calls explicitly, or select the offline mock provider.
        </InlineNotice>
      ) : null}

      <section className="form-section">
        <div className="form-section-heading">
          <h2>Task definition</h2>
          <p>What the agent should produce, and how much authority it has.</p>
        </div>
        <div className="form-grid">
          <label className="field span-2">
            <span className="field-label">Title</span>
            <input
              className="input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              placeholder="Summarize the outcome you need"
              required
            />
          </label>
          <label className="field span-2">
            <span className="field-label">Description</span>
            <textarea
              className="textarea"
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={10000}
              placeholder="Context, constraints, and what a good result looks like."
            />
          </label>
          <label className="field">
            <span className="field-label">Risk class</span>
            <select
              className="select"
              value={risk}
              onChange={(event) => setRisk(event.target.value as TaskPayload['risk_class'] ?? 'low')}
            >
              <option value="low">Low — routine work</option>
              <option value="med">Medium — review recommended</option>
              <option value="high">High — approval + gate abstention checks</option>
            </select>
            <span className="field-hint">
              High-risk tasks require approval and must pass the Strong High-Risk Gate.
            </span>
          </label>
          <label className="field">
            <span className="field-label">Autonomy level</span>
            <select
              className="select"
              value={autonomy}
              onChange={(event) => setAutonomy(Number(event.target.value))}
            >
              {Array.from({ length: settings.max_autonomy_level }, (_, index) => index + 1).map(
                (level) => (
                  <option key={level} value={level}>
                    {level} — {LEVEL_NAMES[level] ?? 'Custom'}
                  </option>
                ),
              )}
            </select>
            <span className="field-hint">
              Global maximum: level {settings.max_autonomy_level}. Change it in Autonomy or Settings.
            </span>
          </label>
          <label className="field">
            <span className="field-label">Output format</span>
            <select
              className="select"
              value={outputFormat}
              onChange={(event) => setOutputFormat(event.target.value as 'text' | 'json')}
            >
              <option value="text">Text</option>
              <option value="json">JSON (validated)</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Demo scenario</span>
            <select
              className="select"
              value={demoScenario}
              onChange={(event) => setDemoScenario(event.target.value)}
              disabled={!isMock}
            >
              <option value="">None — normal execution</option>
              {Object.entries(DEMO_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <span className="field-hint">
              {isMock
                ? 'Mock scenarios exercise real engine failure paths offline.'
                : 'Demo scenarios are available only with the offline mock provider.'}
            </span>
          </label>
        </div>
      </section>

      <section className="form-section">
        <div className="form-section-heading">
          <h2>Execution and budget</h2>
          <p>Server-side limits are enforced before and after every provider call.</p>
        </div>
        <div className="form-grid">
          <label className="field">
            <span className="field-label">Provider</span>
            <select
              className="select"
              value={providerId}
              onChange={(event) => selectProvider(event.target.value)}
            >
              {providers.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.name}
                  {entry.external ? ' (external)' : ' (offline)'}
                </option>
              ))}
            </select>
            {provider ? (
              <span className="field-hint">
                Status: {provider.status.replace('_', ' ')} · key{' '}
                {provider.external ? (provider.key_present ? 'present' : 'missing') : 'not required'}
              </span>
            ) : null}
          </label>
          <label className="field">
            <span className="field-label">Model</span>
            <select className="select" value={model} onChange={(event) => setModel(event.target.value)}>
              {(provider?.models ?? []).map((entry) => (
                <option key={entry} value={entry}>
                  {entry}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Cost budget (USD)</span>
            <input
              className="input"
              type="number"
              min="0.000001"
              step="any"
              value={budget}
              onChange={(event) => setBudget(event.target.value)}
            />
            <span className="field-hint">Maximum ${settings.max_task_budget} per task.</span>
          </label>
          <label className="field">
            <span className="field-label">Token budget</span>
            <input
              className="input"
              type="number"
              min="1"
              step="1"
              value={tokenBudget}
              onChange={(event) => setTokenBudget(event.target.value)}
            />
            <span className="field-hint">Maximum {settings.max_token_budget} tokens.</span>
          </label>
          <label className="field">
            <span className="field-label">Timeout (seconds)</span>
            <input
              className="input"
              type="number"
              min="1"
              step="1"
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(event.target.value)}
            />
            <span className="field-hint">Maximum {settings.max_execution_seconds}s per execution.</span>
          </label>
        </div>
      </section>

      <section className="form-section">
        <div className="form-section-heading">
          <h2>Acceptance criteria</h2>
          <p>
            Deterministic checks run before acceptance. Use plain text, <code>contains:</code>,{' '}
            <code>not_contains:</code>, or <code>regex:</code> prefixes.
          </p>
        </div>
        <div className="criteria-list">
          {criteria.map((criterion, index) => (
            <div key={index} className="criteria-row">
              <input
                className="input"
                value={criterion}
                onChange={(event) => updateCriterion(index, event.target.value)}
                placeholder={
                  index === 0 ? 'e.g. contains:CREST or a required phrase' : 'Additional criterion'
                }
                maxLength={500}
              />
              <button
                type="button"
                className="btn btn-icon btn-ghost"
                aria-label={`Remove criterion ${index + 1}`}
                onClick={() =>
                  setCriteria((current) =>
                    current.length === 1
                      ? ['']
                      : current.filter((_, position) => position !== index),
                  )
                }
                disabled={criteria.length === 1 && criterion === ''}
              >
                <Icon name="x" size={16} />
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-sm btn-outline"
            onClick={() => setCriteria((current) => [...current, ''])}
            disabled={criteria.length >= 20}
          >
            <Icon name="plus" size={14} /> Add criterion
          </button>
        </div>
      </section>

      {autonomy === 5 ? (
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Custom policy</h2>
            <p>
              Level 5 requires an explicit policy. It can only narrow permissions; global limits and
              high-risk approval still apply.
            </p>
          </div>
          <label className="field">
            <span className="field-label">Policy JSON</span>
            <textarea
              className="textarea code-textarea"
              rows={12}
              value={customPolicy}
              onChange={(event) => setCustomPolicy(event.target.value)}
              spellCheck={false}
            />
            <span className="field-hint">
              Allowed keys: allowed_actions, allowed_providers, allowed_models, allowed_risk_classes,
              require_approval, max_cost, max_tokens, timeout_seconds, notes.
            </span>
          </label>
        </section>
      ) : null}

      <div className="form-footer">
        <div className="form-footer-left">
          {allowExecuteNow ? (
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={executeNow}
                onChange={(event) => setExecuteNow(event.target.checked)}
              />
              <span>Execute immediately after creating</span>
            </label>
          ) : null}
          {onCancel ? (
            <button type="button" className="btn btn-outline" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
          ) : null}
        </div>
        <button type="submit" className="btn btn-primary" disabled={busy || !model}>
          {busy ? 'Working…' : submitLabel}
          {!busy ? <Icon name={mode === 'create' ? 'arrow-right' : 'check'} size={16} /> : null}
        </button>
      </div>
    </form>
  );
}

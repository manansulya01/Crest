import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
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

export function AutonomyPage() {
  const { notify } = useToast();
  const autonomy = useApi(() => api.autonomy(), []);
  const [maxLevel, setMaxLevel] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const settings = autonomy.data?.settings;
  const effectiveMax = maxLevel ?? settings?.max_autonomy_level ?? 3;

  async function saveMax() {
    if (!settings) return;
    setBusy(true);
    setError(null);
    try {
      await api.settings.update({
        max_autonomy_level: effectiveMax,
        default_autonomy_level: Math.min(settings.default_autonomy_level, effectiveMax),
      });
      notify('Global autonomy limit updated.', 'success');
      setMaxLevel(null);
      autonomy.reload();
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
        title="Autonomy and permissions"
        description="Five server-enforced levels. Higher autonomy expands what the agent may attempt; it never removes budgets, verification, approval, or the High-Risk Gate."
        actions={
          <Link to="/app/settings" className="btn btn-outline btn-sm">
            <Icon name="settings" size={15} /> Advanced settings
          </Link>
        }
      />

      {autonomy.error ? <ErrorState message={autonomy.error} onRetry={autonomy.reload} /> : null}
      {autonomy.loading && !autonomy.data ? <LoadingBlock label="Loading autonomy policy…" /> : null}

      {autonomy.data && settings ? (
        <>
          <Card
            title="Global autonomy ceiling"
            subtitle="No task may select a level above this ceiling. The server re-checks it at creation and before every provider call."
          >
            <div className="autonomy-ceiling">
              <label className="field autonomy-select">
                <span className="field-label">Maximum autonomy level</span>
                <select
                  className="select"
                  value={effectiveMax}
                  onChange={(event) => setMaxLevel(Number(event.target.value))}
                >
                  {autonomy.data.levels.map((level) => (
                    <option key={level.level} value={level.level}>
                      {level.level} — {level.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void saveMax()}
                disabled={busy || effectiveMax === settings.max_autonomy_level}
              >
                {busy ? 'Saving…' : 'Save ceiling'}
              </button>
            </div>
            {effectiveMax >= 4 ? (
              <InlineNotice tone="warn" title="Elevated autonomy" icon="alert">
                Levels 4 and 5 allow adaptation or custom task policies. They are intended for
                deliberate, supervised use. Custom policies can only narrow permissions, and the
                global high-risk approval requirement still applies.
              </InlineNotice>
            ) : (
              <p className="muted small">
                Level 3 (Bounded) is the default. Levels 4 and 5 require explicit elevation here or in
                Settings.
              </p>
            )}
            {error ? (
              <InlineNotice tone="danger" title="Could not update the ceiling" icon="alert">
                {error}
              </InlineNotice>
            ) : null}
          </Card>

          <div className="level-grid">
            {autonomy.data.levels.map((level) => {
              const enabled = level.level <= settings.max_autonomy_level;
              const isDefault = level.level === settings.default_autonomy_level;
              return (
                <article
                  key={level.level}
                  className={`level-card ${enabled ? '' : 'level-card-disabled'} ${isDefault ? 'level-card-default' : ''}`.trim()}
                >
                  <div className="level-head">
                    <span className="level-number">{level.level}</span>
                    <div>
                      <h2>{level.name}</h2>
                      <span className="level-state">
                        {enabled ? 'Available' : 'Above global ceiling'}
                        {isDefault ? ' · default' : ''}
                      </span>
                    </div>
                    <Badge tone={enabled ? 'success' : 'neutral'}>{enabled ? 'Enabled' : 'Locked'}</Badge>
                  </div>
                  <p className="level-summary">{level.summary}</p>
                  <div className="level-actions">
                    <span className="field-label">Default actions</span>
                    <div className="chip-row">
                      {level.default_actions.map((action) => (
                        <Badge key={action} tone="neutral">
                          {titleCase(action)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="level-approval">
                    <Icon name="shield" size={15} />
                    <span>{level.approval}</span>
                  </div>
                  {!level.can_execute ? (
                    <div className="level-note">Observe mode cannot call providers.</div>
                  ) : null}
                </article>
              );
            })}
          </div>

          <Card
            title="What is enforced where"
            subtitle="The UI is a client; the engine is the authority"
          >
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Control</th>
                    <th>Enforced by</th>
                    <th>Behavior</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Autonomy ceiling</td>
                    <td>Task creation, task update, every execution step</td>
                    <td>Fails closed with AUTONOMY_EXCEEDS_GLOBAL_MAX</td>
                  </tr>
                  <tr>
                    <td>Custom policy</td>
                    <td>Policy module at level 5</td>
                    <td>Only narrows; unknown actions and keys are rejected</td>
                  </tr>
                  <tr>
                    <td>Budgets</td>
                    <td>Pre-flight and post-call checks</td>
                    <td>Stops before spending; fails closed if exceeded</td>
                  </tr>
                  <tr>
                    <td>Approvals</td>
                    <td>Engine, bound to policy fingerprint</td>
                    <td>Expires after one hour; edits invalidate approvals</td>
                  </tr>
                  <tr>
                    <td>Verification</td>
                    <td>Deterministic checks before acceptance</td>
                    <td>Failure is reported as failed, never completed</td>
                  </tr>
                  <tr>
                    <td>High-Risk Gate</td>
                    <td>Strong High-Risk Gate after verification</td>
                    <td>Abstains when independent evidence is insufficient</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Permission matrix" subtitle="Current global settings applied to each level">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Level</th>
                    <th>Execution</th>
                    <th>High-risk approval</th>
                    <th>External approval</th>
                    <th>External calls</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {autonomy.data.matrix.map((row) => (
                    <tr key={row.level}>
                      <td>
                        <strong>
                          {row.level} — {row.name}
                        </strong>
                      </td>
                      <td>{row.can_execute ? 'Allowed' : 'Not allowed'}</td>
                      <td>{row.global_high_risk_approval ? 'Required' : 'Not required'}</td>
                      <td>{row.global_external_approval ? 'Required' : 'Not required'}</td>
                      <td>{row.external_calls_enabled ? 'Enabled' : 'Disabled'}</td>
                      <td>
                        <Badge tone={row.enabled ? 'success' : 'neutral'}>
                          {row.enabled ? 'Available' : 'Locked'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}

      {!autonomy.loading && !autonomy.data && !autonomy.error ? (
        <EmptyState icon="layers" title="Autonomy policy unavailable" />
      ) : null}
    </>
  );
}

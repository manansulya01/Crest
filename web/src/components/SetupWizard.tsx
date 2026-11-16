import { useState } from 'react';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { OperatingMode, OperatingModeId } from '../lib/types';
import { Icon } from './Icons';
import { Modal } from './Modal';
import { Badge, InlineNotice, LoadingBlock } from './UI';

const STEP_LABELS = ['Welcome', 'Operating mode', 'Ready'];

/**
 * First-run onboarding. Shown while onboarding_complete is false. It cannot be
 * dismissed with Escape or a backdrop click; the only way through is to choose
 * a mode and confirm. All changes are applied through the API and enforced
 * server-side.
 */
export function SetupWizard() {
  const { notify } = useToast();
  const settingsState = useApi(() => api.settings.get(), []);
  const modesState = useApi(() => api.modes.get(), []);
  const [step, setStep] = useState(0);
  const [mode, setMode] = useState<OperatingModeId>('supervised');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const settings = settingsState.data;
  const modes: OperatingMode[] = modesState.data?.modes ?? [];

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await api.settings.update({ onboarding_complete: true, operating_mode: mode });
      await api.control.resume().catch(() => undefined);
      settingsState.reload();
      notify('Setup complete. CREST is ready for use.', 'success');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  // Loading or already onboarded — render nothing.
  if (settingsState.loading && !settings) return null;
  if (settings?.onboarding_complete) return null;

  const selected = modes.find((item) => item.id === mode);

  return (
    <Modal
      open
      title="Welcome to CREST"
      subtitle="First-run setup · 3 short steps"
      onClose={() => undefined}
      wide
      footer={
        <>
          <span className="muted small">Step {step + 1} of {STEP_LABELS.length}</span>
          <div className="wizard-footer-actions">
            {step > 0 ? (
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setStep((value) => value - 1)}
                disabled={busy}
              >
                Back
              </button>
            ) : null}
            {step < STEP_LABELS.length - 1 ? (
              <button type="button" className="btn btn-primary" onClick={() => setStep((value) => value + 1)}>
                Continue <Icon name="arrow-right" size={15} />
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => void finish()} disabled={busy}>
                {busy ? 'Saving…' : 'Finish setup'}
              </button>
            )}
          </div>
        </>
      }
    >
      <ol className="wizard-steps" aria-label="Setup progress">
        {STEP_LABELS.map((label, index) => (
          <li key={label} className={index === step ? 'active' : index < step ? 'done' : ''}>
            <span className="wizard-step-dot">{index < step ? <Icon name="check" size={12} /> : index + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {error ? (
        <InlineNotice tone="danger" title="Setup could not be saved" icon="alert">
          {error}
        </InlineNotice>
      ) : null}

      {step === 0 ? (
        <div className="wizard-body">
          <div className="wizard-hero-icon">
            <Icon name="shield" size={34} />
          </div>
          <h3>Local-first, supervised by default</h3>
          <p className="muted">
            CREST runs on this machine. The offline mock provider works immediately — no account,
            network, or API key is required. External providers stay disabled until you explicitly
            enable them and add credentials.
          </p>
          <div className="wizard-points">
            <div><Icon name="check" size={16} /> Budgets, timeouts, and verification are enforced by the backend.</div>
            <div><Icon name="check" size={16} /> High-risk actions always require a human decision.</div>
            <div><Icon name="check" size={16} /> Credentials are encrypted with Windows DPAPI, never stored in plain text.</div>
            <div><Icon name="check" size={16} /> Your data stays in a local database with verified backups.</div>
          </div>
          <InlineNotice tone="warn" title="Honest scope" icon="info">
            CREST is a supervised personal tool (Level 3), not a production safety guarantee.
            Evidence is content-addressed but not cryptographically signed. Keep critical decisions
            under human review.
          </InlineNotice>
        </div>
      ) : null}

      {step === 1 ? (
        <div className="wizard-body">
          <h3>Choose how CREST should act</h3>
          <p className="muted">
            You can change this at any time in Autonomy. High-risk actions stay gated in every mode.
          </p>
          {modesState.loading && !modes.length ? (
            <LoadingBlock label="Loading modes…" />
          ) : (
            <div className="wizard-mode-list" role="radiogroup" aria-label="Operating mode">
              {modes.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={mode === item.id}
                  className={`wizard-mode ${mode === item.id ? 'selected' : ''}`.trim()}
                  onClick={() => setMode(item.id)}
                >
                  <span className="wizard-mode-radio" />
                  <span>
                    <span className="wizard-mode-title">
                      <strong>{item.name}</strong>
                      {item.id === 'supervised' ? <Badge tone="accent">Recommended</Badge> : null}
                    </span>
                    <span className="muted small">{item.summary}</span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {step === 2 ? (
        <div className="wizard-body">
          <div className="wizard-hero-icon">
            <Icon name="check" size={34} />
          </div>
          <h3>You're ready</h3>
          <p className="muted">
            Starting in <strong>{selected?.name ?? 'Supervised'}</strong> mode with the offline mock
            provider. Open <strong>Tasks</strong> to run a deterministic demo, or visit
            <strong> Providers</strong> when you want to connect a real provider.
          </p>
          <div className="wizard-summary">
            <div><span>Operating mode</span><strong>{selected?.name ?? 'Supervised'}</strong></div>
            <div><span>External calls</span><strong>Disabled</strong></div>
            <div><span>Credential storage</span><strong>Windows DPAPI / local encrypted fallback</strong></div>
            <div><span>Safety posture</span><strong>Level 3 — supervised personal use</strong></div>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

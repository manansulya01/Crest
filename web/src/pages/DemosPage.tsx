import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { TaskPayload } from '../lib/types';
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

interface DemoDefinition {
  id: string;
  title: string;
  description: string;
  expected: string;
  icon: 'check' | 'alert' | 'refresh' | 'budget' | 'lock' | 'shield' | 'gate' | 'layers';
  payload: TaskPayload;
  requiresLevel5?: boolean;
}

const DEMOS: DemoDefinition[] = [
  {
    id: 'success',
    title: 'Successful offline execution',
    description:
      'Runs a low-risk task through planning, provider call, deterministic verification, gate evaluation, and audit.',
    expected: 'Completed · verification passed · gate ACCEPT',
    icon: 'check',
    payload: {
      title: 'Offline success demo',
      description: 'Demonstrate a complete CREST execution using the deterministic mock provider.',
      risk_class: 'low',
      autonomy_level: 3,
      provider: 'mock',
      model: 'mock-fast',
      acceptance_criteria: ['CREST'],
    },
  },
  {
    id: 'verification_failure',
    title: 'Verification failure',
    description:
      'The mock provider returns an output that intentionally fails the deterministic failure-phrase check.',
    expected: 'Failed · verification failed · never reported as complete',
    icon: 'alert',
    payload: {
      title: 'Offline verification failure demo',
      description: 'Show that a failed verification is recorded as failed.',
      risk_class: 'low',
      autonomy_level: 3,
      provider: 'mock',
      model: 'mock-fast',
      demo_scenario: 'verification_failure',
    },
  },
  {
    id: 'recovery',
    title: 'Recovery retry',
    description:
      'The first mock attempt fails verification; the engine performs a bounded recovery retry and verifies again.',
    expected: 'Completed after a recorded recovery attempt',
    icon: 'refresh',
    payload: {
      title: 'Offline recovery demo',
      description: 'Demonstrate bounded recovery after a verification failure.',
      risk_class: 'low',
      autonomy_level: 3,
      provider: 'mock',
      model: 'mock-fast',
      demo_scenario: 'recovery',
    },
  },
  {
    id: 'budget',
    title: 'Budget exhaustion',
    description:
      'A five-token budget is too small for the pre-flight estimate, so the engine stops before spending.',
    expected: 'Budget exhausted · no accepted result',
    icon: 'budget',
    payload: {
      title: 'Offline budget exhaustion demo',
      description: 'Demonstrate fail-closed budget enforcement.',
      risk_class: 'low',
      autonomy_level: 3,
      provider: 'mock',
      model: 'mock-fast',
      token_budget: 5,
    },
  },
  {
    id: 'observe',
    title: 'Observe-mode denial',
    description:
      'Autonomy level 1 permits planning but not provider calls. The server denies execution.',
    expected: 'Denied · OBSERVE_MODE_NO_EXECUTION',
    icon: 'lock',
    payload: {
      title: 'Offline observe denial demo',
      description: 'Show that observe mode cannot execute.',
      risk_class: 'low',
      autonomy_level: 1,
      provider: 'mock',
      model: 'mock-fast',
    },
  },
  {
    id: 'approval',
    title: 'Assisted approval',
    description:
      'Autonomy level 2 pauses before the provider call and requests a fresh human approval.',
    expected: 'Awaiting approval · approve in the Approvals queue to continue',
    icon: 'shield',
    payload: {
      title: 'Offline approval demo',
      description: 'Show the assisted-mode approval gate.',
      risk_class: 'low',
      autonomy_level: 2,
      provider: 'mock',
      model: 'mock-fast',
    },
  },
  {
    id: 'high_risk',
    title: 'High-risk gate abstention',
    description:
      'A high-risk task requires approval first. After approval, mock-only evidence is insufficient for the Strong High-Risk Gate, so CREST abstains.',
    expected: 'Awaiting approval → after approval, ABSTAIN with the output retained for inspection',
    icon: 'gate',
    payload: {
      title: 'Offline high-risk abstention demo',
      description: 'Demonstrate the Strong High-Risk Gate with insufficient independent evidence.',
      risk_class: 'high',
      autonomy_level: 3,
      provider: 'mock',
      model: 'mock-fast',
    },
  },
  {
    id: 'custom_policy',
    title: 'Custom-policy denial',
    description:
      'Level 5 with a policy that only allows planning. The provider call is rejected before any execution.',
    expected: 'Denied · ACTION_NOT_IN_CUSTOM_POLICY',
    icon: 'layers',
    requiresLevel5: true,
    payload: {
      title: 'Offline custom-policy denial demo',
      description: 'Show that a custom policy narrows permissions.',
      risk_class: 'low',
      autonomy_level: 5,
      provider: 'mock',
      model: 'mock-fast',
      custom_policy: { allowed_actions: ['plan'] },
    },
  },
];

interface DemoResult {
  taskId: string;
  status: string;
  message: string;
  gate?: string | null;
  verification?: string | null;
}

export function DemosPage() {
  const { notify } = useToast();
  const settings = useApi(() => api.settings.get(), []);
  const providers = useApi(() => api.providers.list(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, DemoResult>>({});
  const [error, setError] = useState<string | null>(null);

  const maxLevel = settings.data?.max_autonomy_level ?? 3;
  const customPolicies = settings.data?.allow_custom_policies ?? false;

  async function runDemo(demo: DemoDefinition) {
    setBusy(demo.id);
    setError(null);
    try {
      const created = await api.tasks.create({
        ...demo.payload,
        title: `${demo.payload.title} · ${new Date().toLocaleTimeString()}`,
        description: demo.payload.description ?? '',
      });
      let task = created;
      try {
        const response = await api.tasks.execute(created.id, true);
        task = 'task' in response ? response.task : response;
      } catch (caught) {
        // Policy denials still persist the task state; fetch it to show the real outcome.
        const message = caught instanceof Error ? caught.message : String(caught);
        try {
          task = await api.tasks.get(created.id);
        } catch {
          // Keep the created task if the detail fetch also fails.
        }
        if (task.status !== 'denied') {
          setError(message);
        }
      }
      const result: DemoResult = {
        taskId: created.id,
        status: task.status,
        message:
          task.status === 'awaiting_approval'
            ? 'The task is waiting for a human decision. Open the task or the Approvals queue to continue.'
            : task.status === 'denied'
              ? task.error ?? 'Execution was denied by policy.'
              : task.status === 'abstained'
                ? task.gate_reason ?? 'The High-Risk Gate abstained.'
                : task.status === 'completed'
                  ? task.verification_status === 'passed'
                    ? 'Execution completed and verification passed.'
                    : 'Execution completed.'
                  : task.status === 'queued' || task.status === 'running'
                    ? 'Execution is still running. Open the task to follow its progress.'
                    : task.error ?? 'Execution finished without an accepted result.',
        gate: task.gate_decision,
        verification: task.verification_status,
      };
      setResults((current) => ({ ...current, [demo.id]: result }));
      notify(`${demo.title}: ${titleCase(task.status)}.`, task.status === 'completed' ? 'success' : 'info');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  const loading = settings.loading || providers.loading;
  const loadError = settings.error || providers.error;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Offline demos"
        description="Exercise the real engine, policy, verification, recovery, approval, budget, and gate paths without network calls or provider spend."
        actions={
          <Link to="/app/tasks" className="btn btn-outline btn-sm">
            View all tasks
          </Link>
        }
      />

      <InlineNotice tone="info" title="What is simulated" icon="flask">
        The provider is a deterministic offline mock. Every output is labelled as simulated. The
        failure paths, budget checks, policy denials, approvals, recovery, verification, gate
        decisions, and audit records are produced by the real CREST engine.
      </InlineNotice>

      {loadError ? (
        <ErrorState
          message={loadError}
          onRetry={() => {
            settings.reload();
            providers.reload();
          }}
        />
      ) : null}
      {error ? (
        <InlineNotice tone="danger" title="Demo could not run" icon="alert">
          {error}
        </InlineNotice>
      ) : null}
      {loading && !settings.data ? <LoadingBlock label="Loading demo configuration…" /> : null}

      {settings.data && providers.data ? (
        <div className="demo-grid">
          {DEMOS.map((demo) => {
            const locked = demo.requiresLevel5 && (maxLevel < 5 || !customPolicies);
            const result = results[demo.id];
            return (
              <Card key={demo.id} className={`demo-card ${locked ? 'demo-locked' : ''}`.trim()}>
                <div className="demo-head">
                  <span className="demo-icon">
                    <Icon name={demo.icon} size={20} />
                  </span>
                  <div>
                    <h2>{demo.title}</h2>
                    <Badge tone={locked ? 'neutral' : 'success'}>{locked ? 'Locked' : 'Ready'}</Badge>
                  </div>
                </div>
                <p className="demo-description">{demo.description}</p>
                <div className="demo-expected">
                  <span className="field-label">Expected path</span>
                  <span>{demo.expected}</span>
                </div>
                {locked ? (
                  <InlineNotice tone="warn" title="Requires elevation" icon="lock">
                    Set the global autonomy ceiling to level 5 and enable custom policies in{' '}
                    <Link to="/app/autonomy">Autonomy</Link> or <Link to="/app/settings">Settings</Link>.
                  </InlineNotice>
                ) : null}
                <div className="demo-actions">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => void runDemo(demo)}
                    disabled={locked || busy !== null}
                  >
                    <Icon name="play" size={15} />
                    {busy === demo.id ? 'Running…' : 'Run demo'}
                  </button>
                  {result ? (
                    <Link to={`/app/tasks/${result.taskId}`} className="btn btn-outline btn-sm">
                      Open task
                    </Link>
                  ) : null}
                </div>
                {result ? (
                  <div className="demo-result">
                    <div className="demo-result-head">
                      <StatusBadge status={result.status} />
                      {result.verification ? (
                        <StatusBadge status={result.verification} label={`Verification ${result.verification}`} />
                      ) : null}
                      {result.gate ? <Badge tone={result.gate === 'ACCEPT' ? 'success' : 'warn'}>{result.gate}</Badge> : null}
                    </div>
                    <p>{result.message}</p>
                    {result.status === 'awaiting_approval' ? (
                      <Link to="/app/approvals" className="btn btn-xs btn-outline">
                        Go to approvals
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      ) : null}
    </>
  );
}

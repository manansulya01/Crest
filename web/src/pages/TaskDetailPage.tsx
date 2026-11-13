import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import {
  formatCost,
  formatDateTime,
  formatNumber,
  percent,
  relativeTime,
  shortId,
  titleCase,
} from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { Task, TaskPayload } from '../lib/types';
import { unwrapExecution } from '../lib/types';
import { Icon } from '../components/Icons';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { ConfirmDialog, Modal } from '../components/Modal';
import { TaskForm } from '../components/TaskForm';
import {
  Badge,
  Card,
  CopyButton,
  EmptyState,
  ErrorState,
  GateBadge,
  InlineNotice,
  LoadingBlock,
  MetaList,
  PageHeader,
  Progress,
  RiskBadge,
  StatusBadge,
} from '../components/UI';

type Tab = 'overview' | 'evidence' | 'audit' | 'raw';

interface Check {
  name: string;
  kind: string;
  status: string;
  detail: string;
  required: boolean;
}

interface GateData {
  decision?: string;
  reason?: string;
  evidence_sources?: number;
  has_deterministic_check?: boolean;
}

function parseJson<T>(value: string | null | undefined): T | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

function latestEvidence(task: Task, kind: string) {
  const matches = (task.evidence ?? []).filter((item) => item.kind === kind);
  return matches.length ? matches[matches.length - 1] : null;
}

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { notify } = useToast();
  const [tab, setTab] = useState<Tab>('overview');
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [approvalDecision, setApprovalDecision] = useState<'approve' | 'reject' | null>(null);
  const [approvalNote, setApprovalNote] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);

  const taskState = useApi(
    () => api.tasks.get(taskId as string),
    [taskId],
    { enabled: Boolean(taskId), pollMs: 5000 },
  );
  const settings = useApi(() => api.settings.get(), []);
  const providers = useApi(() => api.providers.list(), []);

  const task = taskState.data;

  async function runAction(label: string, action: () => Promise<unknown>, success: string) {
    setBusy(label);
    setActionError(null);
    try {
      await action();
      notify(success, 'success');
      taskState.reload();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setActionError(message);
      notify(message, 'error');
    } finally {
      setBusy(null);
    }
  }

  async function handleExecute() {
    if (!task) return;
    setBusy('execute');
    setActionError(null);
    try {
      const response = await api.tasks.execute(task.id);
      const updated = unwrapExecution(response);
      notify(
        updated.status === 'awaiting_approval'
          ? 'Task is awaiting approval.'
          : 'Execution started. This page refreshes automatically.',
        'info',
      );
      taskState.reload();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setActionError(message);
      notify(message, 'error');
    } finally {
      setBusy(null);
    }
  }

  async function submitApproval() {
    if (!task || !approvalDecision) return;
    setBusy('approval');
    setActionError(null);
    try {
      await api.tasks.approve(task.id, {
        decision: approvalDecision,
        note: approvalNote,
        start_execution: approvalDecision === 'approve',
        wait: false,
      });
      notify(
        approvalDecision === 'approve'
          ? 'Approved. Execution will continue under the same policy fingerprint.'
          : 'Task rejected.',
        approvalDecision === 'approve' ? 'success' : 'info',
      );
      setApprovalDecision(null);
      setApprovalNote('');
      taskState.reload();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      setActionError(message);
      notify(message, 'error');
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete() {
    if (!task) return;
    setBusy('delete');
    try {
      await api.tasks.remove(task.id);
      notify('Task deleted. History remains in the audit log.', 'success');
      navigate('/app/tasks');
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : String(caught), 'error');
      setBusy(null);
    }
  }

  async function handleUpdate(payload: TaskPayload) {
    if (!task) return;
    setBusy('save');
    try {
      await api.tasks.update(task.id, payload);
      notify('Task updated. Approvals were reset.', 'success');
      setEditing(false);
      taskState.reload();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : String(caught));
      notify(caught instanceof Error ? caught.message : String(caught), 'error');
    } finally {
      setBusy(null);
    }
  }

  if (!taskId) {
    return <ErrorState message="No task id was provided." />;
  }
  if (taskState.loading && !task) return <LoadingBlock label="Loading task…" />;
  if (taskState.error && !task) {
    return <ErrorState message={taskState.error} onRetry={taskState.reload} />;
  }
  if (!task) return <ErrorState message="Task not found." />;

  if (editing) {
    return (
      <>
        <PageHeader
          eyebrow="Edit task"
          title={task.title}
          description="Saving resets the task to pending and expires outstanding approvals."
          actions={
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(false)}>
              Cancel edit
            </button>
          }
        />
        {settings.data && providers.data ? (
          <Card>
            <TaskForm
              mode="edit"
              initial={task}
              settings={settings.data}
              providers={providers.data}
              busy={busy === 'save'}
              submitLabel="Save changes"
              onCancel={() => setEditing(false)}
              onSubmit={handleUpdate}
            />
          </Card>
        ) : (
          <LoadingBlock label="Loading settings…" />
        )}
      </>
    );
  }

  const running = task.status === 'queued' || task.status === 'running';
  const awaiting = task.status === 'awaiting_approval';
  const verificationData = parseJson<{ checks: Check[]; passed: boolean; independent_sources: number }>(
    latestEvidence(task, 'deterministic_verification')?.content,
  );
  const gateData = parseJson<GateData>(latestEvidence(task, 'gate_decision')?.content);
  const evidence = task.evidence ?? [];
  const independentEvidence = evidence.filter((item) => item.independent).length;
  const executions = task.executions ?? [];
  const approvals = task.approvals ?? [];
  const events = task.events ?? [];
  const result = task.result ?? '';
  const costRatio = task.budget > 0 ? task.cost / task.budget : 0;
  const tokenUsed = task.input_tokens + task.output_tokens;

  return (
    <>
      <div className="breadcrumbs">
        <Link to="/app/tasks">Tasks</Link>
        <Icon name="chevron-right" size={13} />
        <span>{shortId(task.id)}</span>
      </div>

      <PageHeader
        eyebrow={`Task · ${shortId(task.id)}`}
        title={task.title}
        description={task.description || 'No description was provided.'}
        actions={
          <div className="action-row">
            {awaiting ? (
              <>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => setApprovalDecision('approve')}
                  disabled={busy !== null}
                >
                  <Icon name="check" size={15} /> Approve
                </button>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => setApprovalDecision('reject')}
                  disabled={busy !== null}
                >
                  <Icon name="x" size={15} /> Reject
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleExecute}
                disabled={running || busy !== null}
              >
                <Icon name="play" size={15} /> {task.status === 'pending' ? 'Execute' : 'Run again'}
              </button>
            )}
            {running ? (
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() =>
                  void runAction('cancel', () => api.tasks.cancel(task.id), 'Cancellation requested.')
                }
                disabled={busy !== null}
              >
                Cancel
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() =>
                void runAction('plan', () => api.tasks.plan(task.id), 'Plan generated.')
              }
              disabled={busy !== null}
            >
              <Icon name="layers" size={15} /> Plan
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() =>
                void runAction('report', () => api.tasks.report(task.id), 'Report downloaded.')
              }
              disabled={busy !== null}
            >
              <Icon name="download" size={15} /> Report
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => setEditing(true)}
              disabled={running}
            >
              <Icon name="edit" size={15} /> Edit
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm btn-danger-text"
              onClick={() => setDeleteOpen(true)}
              disabled={running}
            >
              <Icon name="trash" size={15} />
            </button>
          </div>
        }
      />

      <div className="badge-row">
        <StatusBadge status={task.status} />
        <RiskBadge risk={task.risk_class} />
        <Badge tone="neutral">Autonomy L{task.autonomy_level}</Badge>
        <GateBadge decision={task.gate_decision} />
        {task.is_mock ? <Badge tone="info">Offline mock</Badge> : null}
        {task.demo_scenario ? <Badge tone="warn">Demo: {titleCase(task.demo_scenario)}</Badge> : null}
      </div>

      {actionError ? (
        <InlineNotice tone="danger" title="Action failed" icon="alert">
          {actionError}
        </InlineNotice>
      ) : null}

      {running ? (
        <InlineNotice tone="info" title="Execution in progress" icon="clock">
          This page refreshes every few seconds. Closing the browser does not stop the server-side
          execution; a restart marks interrupted runs as interrupted rather than complete.
        </InlineNotice>
      ) : null}

      {awaiting ? (
        <InlineNotice tone="warn" title="Human decision required" icon="shield">
          Execution is paused. Approval is bound to the current policy fingerprint and expires after
          one hour. Approving does not bypass verification or the High-Risk Gate.
        </InlineNotice>
      ) : null}

      <div className="detail-grid">
        <div className="detail-main">
          <div className="tabs" role="tablist" aria-label="Task detail sections">
            {(
              [
                ['overview', 'Overview', 'layers'],
                ['evidence', `Evidence (${evidence.length})`, 'evidence'],
                ['audit', `Audit (${events.length})`, 'audit'],
                ['raw', 'Raw JSON', 'terminal'],
              ] as Array<[Tab, string, 'layers' | 'evidence' | 'audit' | 'terminal']>
            ).map(([value, label, icon]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                className={`tab ${tab === value ? 'active' : ''}`.trim()}
                onClick={() => setTab(value)}
              >
                <Icon name={icon} size={15} /> {label}
              </button>
            ))}
          </div>

          {tab === 'overview' ? (
            <div className="stack">
              <Card
                title="Result"
                subtitle={
                  task.result_hash ? `SHA-256 ${task.result_hash.slice(0, 24)}…` : 'No accepted result'
                }
                actions={
                  result ? (
                    <>
                      <CopyButton value={result} label="Copy result" />
                      {task.result_hash ? <CopyButton value={task.result_hash} label="Copy hash" /> : null}
                    </>
                  ) : null
                }
              >
                {result ? (
                  <>
                    <pre className="result-box">{result}</pre>
                    {task.is_mock ? (
                      <p className="result-note">
                        <Icon name="flask" size={14} /> This output came from the offline mock
                        provider. It is simulated and is not evidence of live model reliability.
                      </p>
                    ) : null}
                    {task.error ? (
                      <p className="result-note result-note-warn">
                        <Icon name="alert" size={14} /> {task.error}
                      </p>
                    ) : null}
                  </>
                ) : (
                  <EmptyState
                    icon="terminal"
                    title="No result yet"
                    description={
                      task.status === 'pending'
                        ? 'Run the task to generate a result, verification evidence, and a gate decision.'
                        : task.error || 'This execution did not produce an accepted result.'
                    }
                  />
                )}
              </Card>

              <Card title="Verification" subtitle="Deterministic checks run before acceptance">
                {!task.verification_status ? (
                  <EmptyState
                    icon="check"
                    title="Verification has not run"
                    description="Verification runs after a provider output is produced."
                  />
                ) : (
                  <>
                    <div className="badge-row">
                      <StatusBadge
                        status={task.verification_status}
                        label={`Verification ${task.verification_status}`}
                      />
                      {verificationData ? (
                        <Badge tone="neutral">
                          {verificationData.checks?.length ?? 0} checks ·{' '}
                          {verificationData.independent_sources ?? 0} independent source(s)
                        </Badge>
                      ) : null}
                    </div>
                    {verificationData?.checks?.length ? (
                      <ul className="check-list">
                        {verificationData.checks.map((check) => (
                          <li key={check.name}>
                            <span
                              className={`check-icon ${
                                check.status === 'pass' ? 'check-pass' : 'check-fail'
                              }`.trim()}
                            >
                              <Icon name={check.status === 'pass' ? 'check' : 'x'} size={13} />
                            </span>
                            <div>
                              <strong>{titleCase(check.name)}</strong>
                              <small>{check.detail}</small>
                            </div>
                            <Badge tone={check.status === 'pass' ? 'success' : 'danger'}>
                              {check.status}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">
                        Verification evidence is not available for this task record.
                      </p>
                    )}
                  </>
                )}
              </Card>

              <Card title="High-Risk Gate" subtitle="Narrow veto applied to high-risk acceptance">
                {!task.gate_decision ? (
                  <EmptyState
                    icon="gate"
                    title="Gate has not decided"
                    description="The gate evaluates evidence sufficiency after verification."
                  />
                ) : (
                  <>
                    <div className="gate-summary">
                      <GateBadge decision={task.gate_decision} />
                      <div>
                        <strong>{task.gate_reason || titleCase(task.gate_decision)}</strong>
                        <p>
                          {task.gate_decision === 'ACCEPT'
                            ? 'The gate accepted the evidence for this risk class.'
                            : task.gate_decision === 'ABSTAIN'
                              ? 'CREST refused to accept an outcome it could not support with sufficient independent evidence. The output is retained for inspection only.'
                              : 'The gate rejected this execution.'}
                        </p>
                      </div>
                    </div>
                    <MetaList
                      items={[
                        {
                          label: 'Risk class',
                          value: <RiskBadge risk={task.risk_class} />,
                        },
                        {
                          label: 'Evidence sources',
                          value: gateData?.evidence_sources ?? 0,
                        },
                        {
                          label: 'Deterministic check',
                          value: gateData?.has_deterministic_check ? 'Present' : 'Not present',
                        },
                      ]}
                    />
                  </>
                )}
              </Card>

              <Card
                title="Plan"
                subtitle={task.plan ? `Version ${task.plan.version} · ${task.plan.steps.length} steps` : 'No plan yet'}
              >
                {task.plan ? (
                  <ol className="plan-list">
                    {task.plan.steps.map((step, index) => (
                      <li key={step.id}>
                        <span className="plan-index">{index + 1}</span>
                        <div>
                          <strong>{step.name}</strong>
                          <p>{step.description}</p>
                        </div>
                        <Badge tone="neutral">{titleCase(step.action)}</Badge>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <EmptyState
                    icon="layers"
                    title="No plan recorded"
                    description="Generate a plan to see the deterministic steps CREST intends to take."
                    action={
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() =>
                          void runAction('plan', () => api.tasks.plan(task.id), 'Plan generated.')
                        }
                      >
                        Generate plan
                      </button>
                    }
                  />
                )}
              </Card>

              <Card
                title="Executions"
                subtitle={`${executions.length} attempt(s) recorded`}
                padded={false}
              >
                {executions.length === 0 ? (
                  <div className="card-body">
                    <EmptyState icon="terminal" title="No executions yet" />
                  </div>
                ) : (
                  <div className="execution-list">
                    {executions.map((execution) => (
                      <details key={execution.id} className="execution-item" open={execution === executions[executions.length - 1]}>
                        <summary>
                          <div>
                            <strong>Attempt {execution.attempt}</strong>
                            <span className="muted">
                              {execution.provider} / {execution.model} · {relativeTime(execution.started_at)}
                            </span>
                          </div>
                          <div className="execution-summary-right">
                            <StatusBadge status={execution.status} />
                            <span className="muted">
                              {formatNumber(execution.input_tokens + execution.output_tokens)} tokens ·{' '}
                              {formatCost(execution.cost)}
                            </span>
                          </div>
                        </summary>
                        <div className="execution-body">
                          {execution.error ? (
                            <InlineNotice tone="danger" title="Execution error" icon="alert">
                              {execution.error}
                            </InlineNotice>
                          ) : null}
                          <div className="table-wrap">
                            <table className="data-table compact-table">
                              <thead>
                                <tr>
                                  <th>#</th>
                                  <th>Step</th>
                                  <th>Status</th>
                                  <th>Started</th>
                                  <th>Detail</th>
                                </tr>
                              </thead>
                              <tbody>
                                {execution.steps.map((step) => (
                                  <tr key={step.id}>
                                    <td className="muted">{step.seq}</td>
                                    <td>{step.name}</td>
                                    <td>
                                      <StatusBadge status={step.status} />
                                    </td>
                                    <td className="muted nowrap">{formatDateTime(step.started_at)}</td>
                                    <td>
                                      <code className="inline-code">
                                        {Object.keys(step.detail ?? {}).join(', ') || '—'}
                                      </code>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {Object.keys(execution.detail ?? {}).length ? (
                            <pre className="code-panel">{JSON.stringify(execution.detail, null, 2)}</pre>
                          ) : null}
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          ) : null}

          {tab === 'evidence' ? (
            <Card
              title="Evidence ledger"
              subtitle="Content-addressed records with provenance; not signed attestations"
              padded={false}
            >
              {evidence.length === 0 ? (
                <div className="card-body">
                  <EmptyState
                    icon="evidence"
                    title="No evidence recorded"
                    description="Provider output, verification, and gate decisions are recorded as evidence during execution."
                  />
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Kind</th>
                        <th>Source</th>
                        <th>Status</th>
                        <th>Independent</th>
                        <th>Hash</th>
                        <th>Recorded</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.map((item) => (
                        <tr key={item.id} className="clickable-row" onClick={() => setEvidenceId(item.id)}>
                          <td>
                            <strong>{titleCase(item.kind)}</strong>
                          </td>
                          <td className="muted">{item.source_id || item.source_type}</td>
                          <td>
                            <Badge tone={item.status === 'passed' ? 'success' : item.status === 'failed' ? 'danger' : 'neutral'}>
                              {titleCase(item.status)}
                            </Badge>
                          </td>
                          <td>{item.independent ? <Badge tone="success">Yes</Badge> : <span className="muted">No</span>}</td>
                          <td>
                            <code className="inline-code">{item.content_hash.slice(0, 12)}…</code>
                          </td>
                          <td className="muted nowrap">{relativeTime(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          ) : null}

          {tab === 'audit' ? (
            <Card title="Audit trail" subtitle="Server-side events for this task" padded={false}>
              {events.length === 0 ? (
                <div className="card-body">
                  <EmptyState icon="audit" title="No audit events" />
                </div>
              ) : (
                <ul className="audit-list">
                  {events.map((event) => (
                    <li key={event.id}>
                      <div className="audit-marker">
                        <span />
                      </div>
                      <div className="audit-content">
                        <div className="audit-heading">
                          <strong>{titleCase(event.event_type)}</strong>
                          <span className="muted">{formatDateTime(event.timestamp)}</span>
                        </div>
                        <div className="audit-meta">
                          <Badge tone="neutral">{event.actor}</Badge>
                          {event.execution_id ? (
                            <code className="inline-code">exec {event.execution_id.slice(0, 8)}</code>
                          ) : null}
                        </div>
                        {Object.keys(event.detail ?? {}).length ? (
                          <details className="audit-detail">
                            <summary>Detail</summary>
                            <pre className="code-panel">{JSON.stringify(event.detail, null, 2)}</pre>
                          </details>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ) : null}

          {tab === 'raw' ? (
            <Card title="Raw task record" subtitle="Exactly what the API returns for this task">
              <pre className="code-panel raw-json">{JSON.stringify(task, null, 2)}</pre>
            </Card>
          ) : null}
        </div>

        <aside className="detail-side">
          <Card title="Task metadata">
            <MetaList
              items={[
                { label: 'Status', value: <StatusBadge status={task.status} /> },
                { label: 'Risk', value: <RiskBadge risk={task.risk_class} /> },
                { label: 'Autonomy', value: `Level ${task.autonomy_level}` },
                { label: 'Provider', value: task.provider_name ?? task.provider ?? '—' },
                { label: 'Model', value: <code className="inline-code">{task.model ?? '—'}</code> },
                { label: 'Output', value: task.output_format.toUpperCase() },
                { label: 'Created', value: formatDateTime(task.created_at) },
                { label: 'Started', value: formatDateTime(task.started_at) },
                { label: 'Completed', value: formatDateTime(task.completed_at) },
                { label: 'Timeout', value: `${task.timeout_seconds}s` },
              ]}
            />
          </Card>

          <Card title="Budget and usage">
            <div className="budget-block">
              <div className="budget-heading">
                <span>Cost</span>
                <strong>
                  {formatCost(task.cost)} / {formatCost(task.budget)}
                </strong>
              </div>
              <Progress
                value={task.cost}
                max={task.budget}
                tone={costRatio > 0.9 ? 'danger' : costRatio > 0.7 ? 'warn' : 'accent'}
                label={`${percent(Math.min(1, costRatio), 1)} used`}
              />
            </div>
            <div className="budget-block">
              <div className="budget-heading">
                <span>Tokens</span>
                <strong>
                  {formatNumber(tokenUsed)} / {formatNumber(task.token_budget)}
                </strong>
              </div>
              <Progress
                value={tokenUsed}
                max={task.token_budget}
                tone={tokenUsed / task.token_budget > 0.9 ? 'danger' : 'accent'}
                label={`${formatNumber(Math.max(0, task.token_budget - tokenUsed))} remaining`}
              />
            </div>
            <MetaList
              items={[
                { label: 'Input tokens', value: formatNumber(task.input_tokens) },
                { label: 'Output tokens', value: formatNumber(task.output_tokens) },
                { label: 'Cost remaining', value: formatCost(task.budget_remaining ?? 0) },
              ]}
            />
          </Card>

          <Card title="Evidence summary">
            <MetaList
              items={[
                { label: 'Records', value: evidence.length },
                { label: 'Independent', value: independentEvidence },
                { label: 'Verification', value: <StatusBadge status={task.verification_status} label={task.verification_status ? titleCase(task.verification_status) : 'Not run'} /> },
                { label: 'Gate', value: <GateBadge decision={task.gate_decision} /> },
              ]}
            />
            <button type="button" className="btn btn-outline btn-sm btn-block" onClick={() => setTab('evidence')}>
              Open evidence ledger
            </button>
          </Card>

          <Card title="Approvals">
            {approvals.length === 0 ? (
              <p className="muted small">No approval was requested for this task.</p>
            ) : (
              <ul className="approval-history">
                {approvals.map((approval) => (
                  <li key={approval.id}>
                    <div>
                      <strong>{titleCase(approval.action)}</strong>
                      <small>{approval.reason}</small>
                      <small className="muted">Requested {relativeTime(approval.requested_at)}</small>
                    </div>
                    <StatusBadge status={approval.status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Policy fingerprint">
            <p className="muted small">
              Approval is bound to this fingerprint. Editing the task invalidates outstanding
              approvals.
            </p>
            <div className="fingerprint">
              <code>{task.policy_fingerprint ?? '—'}</code>
              {task.policy_fingerprint ? <CopyButton value={task.policy_fingerprint} label="Copy" /> : null}
            </div>
            {task.custom_policy ? (
              <>
                <h3 className="subsection-title">Custom policy</h3>
                <pre className="code-panel compact-code">{JSON.stringify(task.custom_policy, null, 2)}</pre>
              </>
            ) : null}
          </Card>
        </aside>
      </div>

      <Modal
        open={approvalDecision !== null}
        title={approvalDecision === 'approve' ? 'Approve this execution?' : 'Reject this task?'}
        subtitle={
          approvalDecision === 'approve'
            ? 'Approval is bound to the current policy fingerprint and expires after one hour.'
            : 'Rejection ends this task without executing it.'
        }
        onClose={() => {
          setApprovalDecision(null);
          setApprovalNote('');
        }}
        footer={
          <>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                setApprovalDecision(null);
                setApprovalNote('');
              }}
              disabled={busy === 'approval'}
            >
              Cancel
            </button>
            <button
              type="button"
              className={`btn ${approvalDecision === 'approve' ? 'btn-primary' : 'btn-danger'}`}
              onClick={() => void submitApproval()}
              disabled={busy === 'approval'}
            >
              {busy === 'approval'
                ? 'Working…'
                : approvalDecision === 'approve'
                  ? 'Approve execution'
                  : 'Reject task'}
            </button>
          </>
        }
      >
        <label className="field">
          <span className="field-label">Decision note (optional)</span>
          <textarea
            className="textarea"
            rows={3}
            maxLength={2000}
            value={approvalNote}
            onChange={(event) => setApprovalNote(event.target.value)}
            placeholder="Why are you approving or rejecting this action?"
          />
        </label>
        <p className="muted small">
          Approving does not bypass verification, budgets, or the High-Risk Gate. With mock-only
          evidence, a high-risk task will still abstain.
        </p>
      </Modal>

      <ConfirmDialog
        open={deleteOpen}
        title="Delete this task?"
        description="The task is soft-deleted: it disappears from task lists but its audit events remain. Provider credentials are never part of task data."
        confirmLabel="Delete task"
        danger
        busy={busy === 'delete'}
        onConfirm={() => void handleDelete()}
        onClose={() => setDeleteOpen(false)}
      />

      <EvidenceViewer evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </>
  );
}

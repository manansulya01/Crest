import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatDateTime, relativeTime, shortId, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import type { Approval } from '../lib/types';
import { Icon } from '../components/Icons';
import { Modal } from '../components/Modal';
import {
  Badge,
  EmptyState,
  ErrorState,
  InlineNotice,
  PageHeader,
  RiskBadge,
  SkeletonRows,
  StatusBadge,
} from '../components/UI';

export function ApprovalsPage() {
  const { notify } = useToast();
  const [statusFilter, setStatusFilter] = useState('pending');
  const [offset, setOffset] = useState(0);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<{ approval: Approval; decision: 'approve' | 'reject' } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const approvals = useApi(
    () =>
      api.approvals({
        status: statusFilter || undefined,
        limit: 50,
        offset,
      }),
    [statusFilter, offset],
    { pollMs: 15000 },
  );

  async function submitDecision() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.tasks.approve(selected.approval.task_id, {
        decision: selected.decision,
        note: notes[selected.approval.id] ?? '',
        start_execution: selected.decision === 'approve',
        wait: false,
      });
      notify(
        selected.decision === 'approve'
          ? 'Approval granted. The task will continue under its current policy fingerprint.'
          : 'Task rejected.',
        selected.decision === 'approve' ? 'success' : 'info',
      );
      setSelected(null);
      approvals.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Approvals"
        description="Human decisions required by autonomy policy, external providers, high-risk tasks, or custom rules. Approving never bypasses verification or the gate."
        actions={
          <label className="field-inline">
            <span>Show</span>
            <select
              className="select select-sm"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setOffset(0);
              }}
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="expired">Expired</option>
              <option value="">All decisions</option>
            </select>
          </label>
        }
      />

      {error ? (
        <InlineNotice tone="danger" title="Decision failed" icon="alert">
          {error}
        </InlineNotice>
      ) : null}
      {approvals.error ? <ErrorState message={approvals.error} onRetry={approvals.reload} /> : null}
      {approvals.loading && !approvals.data ? <SkeletonRows rows={4} /> : null}

      {approvals.data ? (
        approvals.data.items.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={statusFilter === 'pending' ? 'check' : 'shield'}
              title={statusFilter === 'pending' ? 'No pending approvals' : 'No approvals in this view'}
              description={
                statusFilter === 'pending'
                  ? 'When a task needs a human decision, it will appear here with the exact reason and policy fingerprint.'
                  : 'Try another filter or create a high-risk task to exercise the approval flow.'
              }
              action={
                <Link to="/app/tasks/new" className="btn btn-outline btn-sm">
                  Create a task
                </Link>
              }
            />
          </div>
        ) : (
          <div className="approval-list">
            {approvals.data.items.map((approval) => (
              <article key={approval.id} className="approval-card">
                <div className="approval-card-head">
                  <div>
                    <div className="approval-title-row">
                      <Link to={`/app/tasks/${approval.task_id}`} className="approval-title">
                        {approval.title ?? `Task ${shortId(approval.task_id)}`}
                      </Link>
                      <StatusBadge status={approval.status} />
                      {approval.risk_class ? <RiskBadge risk={approval.risk_class} /> : null}
                      {approval.autonomy_level ? (
                        <Badge tone="neutral">L{approval.autonomy_level}</Badge>
                      ) : null}
                    </div>
                    <p className="approval-reason">{approval.reason}</p>
                  </div>
                  <div className="approval-time">
                    <span>{relativeTime(approval.requested_at)}</span>
                    <small>{formatDateTime(approval.requested_at)}</small>
                  </div>
                </div>

                <div className="approval-meta">
                  <span>
                    <strong>Action</strong> {titleCase(approval.action)}
                  </span>
                  <span>
                    <strong>Route</strong> {approval.provider ?? '—'} / {approval.model ?? '—'}
                  </span>
                  <span>
                    <strong>Task status</strong> {titleCase(approval.task_status)}
                  </span>
                  <span className="mono">
                    <strong>Policy</strong> {approval.policy_fingerprint.slice(0, 16)}…
                  </span>
                </div>

                {approval.status === 'pending' ? (
                  <div className="approval-actions">
                    <label className="field approval-note">
                      <span className="field-label">Decision note (optional)</span>
                      <input
                        className="input"
                        value={notes[approval.id] ?? ''}
                        onChange={(event) =>
                          setNotes((current) => ({ ...current, [approval.id]: event.target.value }))
                        }
                        maxLength={2000}
                        placeholder="Record why you are deciding this way"
                      />
                    </label>
                    <div className="approval-buttons">
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => setSelected({ approval, decision: 'reject' })}
                      >
                        <Icon name="x" size={15} /> Reject
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => setSelected({ approval, decision: 'approve' })}
                      >
                        <Icon name="check" size={15} /> Approve
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="approval-decided">
                    <span>
                      Decided {approval.decided_at ? formatDateTime(approval.decided_at) : '—'}
                      {approval.note ? ` · “${approval.note}”` : ''}
                    </span>
                    <Link to={`/app/tasks/${approval.task_id}`} className="btn btn-xs btn-outline">
                      Open task
                    </Link>
                  </div>
                )}
              </article>
            ))}
          </div>
        )
      ) : null}

      <Modal
        open={selected !== null}
        title={selected?.decision === 'approve' ? 'Approve execution?' : 'Reject this task?'}
        subtitle={
          selected?.decision === 'approve'
            ? 'The task resumes under the policy fingerprint shown below.'
            : 'The task ends without executing the requested action.'
        }
        onClose={() => setSelected(null)}
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => setSelected(null)} disabled={busy}>
              Cancel
            </button>
            <button
              type="button"
              className={`btn ${selected?.decision === 'approve' ? 'btn-primary' : 'btn-danger'}`}
              onClick={() => void submitDecision()}
              disabled={busy}
            >
              {busy ? 'Working…' : selected?.decision === 'approve' ? 'Approve' : 'Reject'}
            </button>
          </>
        }
      >
        {selected ? (
          <div className="stack-sm">
            <p>
              <strong>{selected.approval.title ?? selected.approval.task_id}</strong>
            </p>
            <p className="muted">{selected.approval.reason}</p>
            <div className="fingerprint">
              <code>{selected.approval.policy_fingerprint}</code>
            </div>
            <label className="field">
              <span className="field-label">Decision note (optional)</span>
              <textarea
                className="textarea"
                rows={3}
                value={notes[selected.approval.id] ?? ''}
                onChange={(event) =>
                  setNotes((current) => ({ ...current, [selected.approval.id]: event.target.value }))
                }
                maxLength={2000}
              />
            </label>
            <p className="muted small">
              With mock-only evidence, a high-risk task will still abstain after approval.
            </p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { formatDateTime, formatNumber, shortId, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import {
  Badge,
  EmptyState,
  ErrorState,
  PageHeader,
  Pagination,
  SkeletonRows,
} from '../components/UI';

const PAGE_SIZE = 50;

const EVENT_TYPES = [
  ['', 'All events'],
  ['TASK_CREATED', 'Task created'],
  ['TASK_UPDATED', 'Task updated'],
  ['TASK_DELETED', 'Task deleted'],
  ['PLAN_CREATED', 'Plan created'],
  ['EXECUTION_QUEUED', 'Execution queued'],
  ['EXECUTION_STARTED', 'Execution started'],
  ['APPROVAL_REQUESTED', 'Approval requested'],
  ['APPROVAL_GRANTED', 'Approval granted'],
  ['APPROVAL_REJECTED', 'Approval rejected'],
  ['PROVIDER_ERROR', 'Provider error'],
  ['VERIFICATION_PASSED', 'Verification passed'],
  ['VERIFICATION_FAILED', 'Verification failed'],
  ['RECOVERY_ATTEMPT', 'Recovery attempt'],
  ['GATE_DECISION', 'Gate decision'],
  ['EVIDENCE_RECORDED', 'Evidence recorded'],
  ['EXECUTION_COMPLETED', 'Execution completed'],
  ['EXECUTION_FAILED', 'Execution failed'],
  ['EXECUTION_ABSTAINED', 'Execution abstained'],
  ['BUDGET_EXHAUSTED', 'Budget exhausted'],
  ['POLICY_DENIED', 'Policy denied'],
  ['SETTINGS_UPDATED', 'Settings updated'],
  ['PROVIDER_UPDATED', 'Provider updated'],
  ['ROUTING_UPDATED', 'Routing updated'],
] as const;

export function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const eventType = searchParams.get('event') ?? '';
  const search = searchParams.get('q') ?? '';
  const taskId = searchParams.get('task') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const [searchDraft, setSearchDraft] = useState(search);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    setSearchDraft(search);
  }, [search]);

  const audit = useApi(
    () =>
      api.audit({
        event_type: eventType || undefined,
        search: search || undefined,
        task_id: taskId || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [eventType, search, taskId, offset],
  );

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setSearchParams(next);
  }

  return (
    <>
      <PageHeader
        eyebrow="Evidence"
        title="Audit log"
        description="Append-only server-side history of task, policy, provider, execution, verification, gate, and settings events. Details are redacted before persistence."
        actions={
          <button type="button" className="btn btn-outline btn-sm" onClick={audit.reload}>
            <Icon name="refresh" size={15} /> Refresh
          </button>
        }
      />

      <div className="toolbar toolbar-wrap">
        <div className="toolbar-filters">
          <label className="field-inline">
            <span>Event</span>
            <select
              className="select select-sm"
              value={eventType}
              onChange={(event) => updateParam('event', event.target.value)}
            >
              {EVENT_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            updateParam('q', searchDraft.trim());
          }}
        >
          <span className="search-icon">
            <Icon name="search" size={16} />
          </span>
          <input
            className="input search-input"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Search detail, event, or actor"
            aria-label="Search audit events"
          />
          <button type="submit" className="btn btn-outline btn-sm">
            Search
          </button>
        </form>
      </div>

      {taskId ? (
        <div className="filter-banner">
          <span>
            Showing audit events for task <code className="inline-code">{shortId(taskId)}</code>
          </span>
          <div className="filter-banner-actions">
            <Link to={`/app/tasks/${taskId}`} className="btn btn-xs btn-outline">
              Open task
            </Link>
            <button
              type="button"
              className="btn btn-xs btn-ghost"
              onClick={() => updateParam('task', '')}
            >
              Clear task filter
            </button>
          </div>
        </div>
      ) : null}

      {audit.error ? <ErrorState message={audit.error} onRetry={audit.reload} /> : null}
      {audit.loading && !audit.data ? <SkeletonRows rows={10} /> : null}

      {audit.data ? (
        <div className="card">
          <div className="card-body card-body-flush">
            {audit.data.items.length === 0 ? (
              <EmptyState
                icon="audit"
                title="No matching audit events"
                description="Events are appended as tasks are created, executed, verified, gated, and administered."
              />
            ) : (
              <div className="table-wrap">
                <table className="data-table audit-table">
                  <thead>
                    <tr>
                      <th aria-label="Expand" />
                      <th>Timestamp</th>
                      <th>Event</th>
                      <th>Task</th>
                      <th>Actor</th>
                      <th>Execution</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.data.items.map((event) => (
                      <>
                        <tr
                          key={event.id}
                          className="clickable-row"
                          onClick={() => setExpanded(expanded === event.id ? null : event.id)}
                        >
                          <td>
                            <Icon
                              name={expanded === event.id ? 'chevron-down' : 'chevron-right'}
                              size={14}
                            />
                          </td>
                          <td className="muted nowrap">{formatDateTime(event.timestamp)}</td>
                          <td>
                            <Badge
                              tone={
                                event.event_type.includes('FAILED') ||
                                event.event_type.includes('DENIED') ||
                                event.event_type.includes('ERROR') ||
                                event.event_type.includes('EXHAUSTED')
                                  ? 'danger'
                                  : event.event_type.includes('ABSTAIN') ||
                                      event.event_type.includes('APPROVAL')
                                    ? 'warn'
                                    : event.event_type.includes('COMPLETED') ||
                                        event.event_type.includes('PASSED')
                                      ? 'success'
                                      : 'neutral'
                              }
                            >
                              {titleCase(event.event_type)}
                            </Badge>
                          </td>
                          <td>
                            {event.task_id ? (
                              <Link
                                to={`/app/tasks/${event.task_id}`}
                                className="inline-code"
                                onClick={(clickEvent) => clickEvent.stopPropagation()}
                              >
                                {shortId(event.task_id)}
                              </Link>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td className="muted">{event.actor}</td>
                          <td className="muted">
                            {event.execution_id ? (
                              <code className="inline-code">{shortId(event.execution_id)}</code>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="audit-detail-cell">
                            <span className="muted">
                              {Object.keys(event.detail ?? {}).join(', ') || '—'}
                            </span>
                          </td>
                        </tr>
                        {expanded === event.id ? (
                          <tr key={`${event.id}-detail`} className="audit-expanded-row">
                            <td colSpan={7}>
                              <pre className="code-panel">
                                {JSON.stringify(event.detail ?? {}, null, 2)}
                              </pre>
                            </td>
                          </tr>
                        ) : null}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {audit.data.items.length > 0 ? (
            <div className="card-footer">
              <span className="muted">{formatNumber(audit.data.total)} event(s)</span>
              <Pagination
                total={audit.data.total}
                limit={audit.data.limit}
                offset={audit.data.offset}
                onChange={(nextOffset) => {
                  const next = new URLSearchParams(searchParams);
                  next.set('page', String(Math.floor(nextOffset / PAGE_SIZE) + 1));
                  setSearchParams(next);
                }}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

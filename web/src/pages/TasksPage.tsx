import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { formatCost, formatNumber, relativeTime, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import {
  Badge,
  EmptyState,
  ErrorState,
  GateBadge,
  PageHeader,
  Pagination,
  SkeletonRows,
  StatusBadge,
} from '../components/UI';

const PAGE_SIZE = 20;

export function TasksPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') ?? '';
  const risk = searchParams.get('risk') ?? '';
  const search = searchParams.get('q') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const [searchDraft, setSearchDraft] = useState(search);

  useEffect(() => {
    setSearchDraft(search);
  }, [search]);

  const tasks = useApi(
    () =>
      api.tasks.list({
        status: status || undefined,
        risk_class: risk || undefined,
        search: search || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [status, risk, search, offset],
    { pollMs: 20000 },
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
        eyebrow="Workspace"
        title="Tasks"
        description="Every task, its risk class, autonomy level, verification state, and gate decision."
        actions={
          <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
            <Icon name="plus" size={16} /> New task
          </Link>
        }
      />

      <div className="toolbar">
        <div className="toolbar-filters">
          <label className="field-inline">
            <span>Status</span>
            <select
              className="select select-sm"
              value={status}
              onChange={(event) => updateParam('status', event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="awaiting_approval">Awaiting approval</option>
              <option value="completed">Completed</option>
              <option value="abstained">Abstained</option>
              <option value="failed">Failed</option>
              <option value="denied">Denied</option>
              <option value="budget_exhausted">Budget exhausted</option>
              <option value="cancelled">Cancelled</option>
              <option value="interrupted">Interrupted</option>
            </select>
          </label>
          <label className="field-inline">
            <span>Risk</span>
            <select
              className="select select-sm"
              value={risk}
              onChange={(event) => updateParam('risk', event.target.value)}
            >
              <option value="">All risk classes</option>
              <option value="low">Low</option>
              <option value="med">Medium</option>
              <option value="high">High</option>
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
            placeholder="Search title or description"
            aria-label="Search tasks"
          />
          <button type="submit" className="btn btn-outline btn-sm">
            Search
          </button>
          {search ? (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => updateParam('q', '')}
            >
              Clear
            </button>
          ) : null}
        </form>
      </div>

      {tasks.error ? <ErrorState message={tasks.error} onRetry={tasks.reload} /> : null}
      {tasks.loading && !tasks.data ? <SkeletonRows rows={8} /> : null}

      {tasks.data ? (
        <div className="card">
          <div className="card-body card-body-flush">
            {tasks.data.items.length === 0 ? (
              <EmptyState
                icon="tasks"
                title={search || status || risk ? 'No matching tasks' : 'No tasks yet'}
                description={
                  search || status || risk
                    ? 'Adjust the filters or clear the search to see other tasks.'
                    : 'Create a task to exercise the control plane end to end.'
                }
                action={
                  search || status || risk ? (
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => setSearchParams(new URLSearchParams())}
                    >
                      Clear filters
                    </button>
                  ) : (
                    <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
                      Create a task
                    </Link>
                  )
                }
              />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Task</th>
                      <th>Status</th>
                      <th>Risk</th>
                      <th>Autonomy</th>
                      <th>Route</th>
                      <th>Verification</th>
                      <th>Gate</th>
                      <th>Cost</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.data.items.map((task) => (
                      <tr key={task.id}>
                        <td>
                          <Link to={`/app/tasks/${task.id}`} className="table-title">
                            {task.title}
                          </Link>
                          <span className="table-subtitle">
                            {task.result_preview
                              ? task.result_preview
                              : task.description || 'No description'}
                          </span>
                        </td>
                        <td>
                          <StatusBadge status={task.status} />
                        </td>
                        <td>
                          <Badge
                            tone={
                              task.risk_class === 'high'
                                ? 'danger'
                                : task.risk_class === 'med'
                                  ? 'warn'
                                  : 'success'
                            }
                          >
                            {titleCase(task.risk_class)}
                          </Badge>
                        </td>
                        <td>
                          <Badge tone="neutral">L{task.autonomy_level}</Badge>
                        </td>
                        <td>
                          <span className="route-cell">
                            {task.provider}
                            <small>{task.model}</small>
                          </span>
                        </td>
                        <td>
                          <StatusBadge status={task.verification_status} label={task.verification_status ? titleCase(task.verification_status) : 'Not run'} />
                        </td>
                        <td>
                          <GateBadge decision={task.gate_decision} />
                        </td>
                        <td className="nowrap">{formatCost(task.cost)}</td>
                        <td className="nowrap muted">{relativeTime(task.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {tasks.data.items.length > 0 ? (
            <div className="card-footer">
              <span className="muted">{formatNumber(tasks.data.total)} task(s)</span>
              <Pagination
                total={tasks.data.total}
                limit={tasks.data.limit}
                offset={tasks.data.offset}
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

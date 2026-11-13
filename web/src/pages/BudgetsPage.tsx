import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { formatCost, formatNumber } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Progress,
  SkeletonRows,
  StatCard,
  StatusBadge,
} from '../components/UI';

export function BudgetsPage() {
  const budgets = useApi(() => api.budgets(), [], { pollMs: 30000 });
  const [search, setSearch] = useState('');
  const [onlyHigh, setOnlyHigh] = useState(false);

  const data = budgets.data;
  const tasks = (data?.tasks ?? []).filter((task) => {
    if (search && !task.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (onlyHigh) {
      const costRatio = task.budget > 0 ? task.cost / task.budget : 0;
      const tokenRatio = task.token_budget > 0 ? task.tokens / task.token_budget : 0;
      return costRatio >= 0.8 || tokenRatio >= 0.8;
    }
    return true;
  });

  return (
    <>
      <PageHeader
        eyebrow="Control"
        title="Budgets and usage"
        description="Real spend and token usage recorded by the engine. Limits are enforced before provider calls and re-checked after every response."
        actions={
          <Link to="/app/settings" className="btn btn-outline btn-sm">
            <Icon name="settings" size={15} /> Adjust limits
          </Link>
        }
      />

      {budgets.error ? <ErrorState message={budgets.error} onRetry={budgets.reload} /> : null}
      {budgets.loading && !data ? <SkeletonRows rows={8} /> : null}

      {data ? (
        <>
          <div className="stat-grid">
            <StatCard
              label="Total cost"
              value={formatCost(data.totals.cost)}
              detail={`${formatNumber(data.totals.tasks)} task(s)`}
              icon="budget"
              tone="accent"
            />
            <StatCard
              label="Total tokens"
              value={formatNumber(data.totals.tokens)}
              detail={`${formatNumber(data.totals.input_tokens)} in · ${formatNumber(data.totals.output_tokens)} out`}
              icon="layers"
            />
            <StatCard
              label="Max task budget"
              value={formatCost(data.limits.max_task_budget)}
              detail="Per-task cost ceiling"
              icon="lock"
            />
            <StatCard
              label="Max token budget"
              value={formatNumber(data.limits.max_token_budget)}
              detail={`${data.limits.max_execution_seconds}s max execution`}
              icon="clock"
            />
          </div>

          <div className="two-col">
            <Card title="Default limits" subtitle="Applied to new tasks unless overridden within the ceiling">
              <dl className="limit-list">
                <div>
                  <dt>Default cost budget</dt>
                  <dd>{formatCost(data.limits.default_budget)}</dd>
                </div>
                <div>
                  <dt>Default token budget</dt>
                  <dd>{formatNumber(data.limits.default_token_budget)}</dd>
                </div>
                <div>
                  <dt>Max task budget</dt>
                  <dd>{formatCost(data.limits.max_task_budget)}</dd>
                </div>
                <div>
                  <dt>Max token budget</dt>
                  <dd>{formatNumber(data.limits.max_token_budget)}</dd>
                </div>
                <div>
                  <dt>Max execution time</dt>
                  <dd>{data.limits.max_execution_seconds}s</dd>
                </div>
              </dl>
            </Card>
            <Card title="How budgets fail closed" subtitle="No silent overspend">
              <ul className="plain-list">
                <li>
                  <Icon name="check" size={15} /> A pre-flight estimate stops the run before any
                  provider call if the remaining budget is insufficient.
                </li>
                <li>
                  <Icon name="check" size={15} /> Cost and token usage are recorded after every
                  response, including verifier calls.
                </li>
                <li>
                  <Icon name="check" size={15} /> Exceeding either budget marks the task
                  <code className="inline-code">budget_exhausted</code> and never reports it as
                  complete.
                </li>
                <li>
                  <Icon name="check" size={15} /> The offline mock provider records $0 cost, so token
                  limits are the primary demo constraint.
                </li>
              </ul>
            </Card>
          </div>

          <Card
            title="Per-task usage"
            subtitle={`${tasks.length} shown`}
            actions={
              <div className="inline-filters">
                <input
                  className="input input-sm"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Filter by title"
                  aria-label="Filter budgets by task title"
                />
                <label className="checkbox-field checkbox-compact">
                  <input
                    type="checkbox"
                    checked={onlyHigh}
                    onChange={(event) => setOnlyHigh(event.target.checked)}
                  />
                  <span>≥ 80% used</span>
                </label>
              </div>
            }
            padded={false}
          >
            {data.tasks.length === 0 ? (
              <div className="card-body">
                <EmptyState
                  icon="budget"
                  title="No usage recorded"
                  description="Run a task to see real cost and token consumption."
                  action={
                    <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
                      Create a task
                    </Link>
                  }
                />
              </div>
            ) : tasks.length === 0 ? (
              <div className="card-body">
                <EmptyState
                  icon="filter"
                  title="No tasks match the filter"
                  description="Clear the title filter or the usage threshold."
                />
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Task</th>
                      <th>Status</th>
                      <th>Route</th>
                      <th>Cost usage</th>
                      <th>Token usage</th>
                      <th>Provider</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((task) => (
                      <tr key={task.id}>
                        <td>
                          <Link to={`/app/tasks/${task.id}`} className="table-title">
                            {task.title}
                          </Link>
                        </td>
                        <td>
                          <StatusBadge status={task.status} />
                        </td>
                        <td className="muted">
                          {task.provider} / {task.model}
                        </td>
                        <td>
                          <div className="usage-cell">
                            <span>
                              {formatCost(task.cost)} / {formatCost(task.budget)}
                            </span>
                            <Progress
                              value={task.cost}
                              max={task.budget}
                              tone={task.budget > 0 && task.cost / task.budget >= 0.9 ? 'danger' : 'accent'}
                            />
                          </div>
                        </td>
                        <td>
                          <div className="usage-cell">
                            <span>
                              {formatNumber(task.tokens)} / {formatNumber(task.token_budget)}
                            </span>
                            <Progress
                              value={task.tokens}
                              max={task.token_budget}
                              tone={
                                task.token_budget > 0 && task.tokens / task.token_budget >= 0.9
                                  ? 'danger'
                                  : 'accent'
                              }
                            />
                          </div>
                        </td>
                        <td>
                          <Badge tone={task.provider === 'mock' ? 'info' : 'warn'}>
                            {task.provider === 'mock' ? 'Offline' : 'External'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <p className="page-note">
            <Icon name="info" size={15} />
            <span>
              Cost is only as accurate as the per-provider pricing configured on the Providers page.
              When pricing is not configured, cost is recorded as $0 and token limits remain
              authoritative. The mock provider always costs $0.
            </span>
          </p>
        </>
      ) : null}
    </>
  );
}

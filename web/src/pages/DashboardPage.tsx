import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import {
  formatCost,
  formatNumber,
  percent,
  relativeTime,
  titleCase,
} from '../lib/format';
import { useApi } from '../lib/useApi';
import { Icon } from '../components/Icons';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  GateBadge,
  PageHeader,
  SkeletonRows,
  StatCard,
  StatusBadge,
} from '../components/UI';

export function DashboardPage() {
  const stats = useApi(() => api.stats(), [], { pollMs: 15000 });
  const approvals = useApi(() => api.approvals({ status: 'pending', limit: 5 }), [], {
    pollMs: 15000,
  });
  const diagnostics = useApi(() => api.diagnostics(), [], { pollMs: 60000 });

  const data = stats.data;
  const maxDaily = Math.max(1, ...(data?.daily.map((entry) => entry.count) ?? [1]));

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Live state of the control plane: task outcomes, pending decisions, spending, and recent audit activity."
        actions={
          <>
            <Link to="/app/demos" className="btn btn-outline btn-sm">
              <Icon name="flask" size={16} /> Offline demos
            </Link>
            <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
              <Icon name="plus" size={16} /> New task
            </Link>
          </>
        }
      />

      {stats.error && !data ? <ErrorState message={stats.error} onRetry={stats.reload} /> : null}
      {stats.loading && !data ? (
        <div className="stat-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="skeleton skeleton-stat" />
          ))}
        </div>
      ) : null}

      {data ? (
        <>
          {diagnostics.data && !diagnostics.data.external_calls_enabled ? (
            <div className="offline-banner">
              <div className="offline-banner-icon">
                <Icon name="flask" size={18} />
              </div>
              <div>
                <strong>Offline-first mode</strong>
                <span>
                  External calls are disabled. The mock provider is deterministic and every simulated
                  result is labelled as such. Enable external providers in{' '}
                  <Link to="/app/settings">Settings</Link>.
                </span>
              </div>
              <Badge tone="info">Mock ready</Badge>
            </div>
          ) : null}

          <div className="stat-grid">
            <StatCard
              label="Total tasks"
              value={formatNumber(data.total_tasks)}
              detail={`${data.completed} completed · ${data.failed} failed`}
              icon="tasks"
              tone="accent"
            />
            <StatCard
              label="Awaiting approval"
              value={formatNumber(data.awaiting_approval)}
              detail={
                data.awaiting_approval > 0 ? (
                  <Link to="/app/approvals">Review pending decisions →</Link>
                ) : (
                  'No pending decisions'
                )
              }
              icon="shield"
              tone={data.awaiting_approval > 0 ? 'warn' : 'neutral'}
            />
            <StatCard
              label="Verification pass rate"
              value={percent(data.verification_pass_rate)}
              detail={`${data.verification_passed} passed · ${data.verification_failed} failed`}
              icon="check"
              tone="success"
            />
            <StatCard
              label="Budget used"
              value={formatCost(data.budget_used)}
              detail={`${formatNumber(data.input_tokens + data.output_tokens)} tokens`}
              icon="budget"
              tone="neutral"
            />
          </div>

          <div className="dashboard-grid">
            <Card
              title="Task activity"
              subtitle="Tasks created over the last 14 days"
              actions={<Badge tone="neutral">{formatNumber(data.total_tasks)} total</Badge>}
            >
              {data.daily.length === 0 ? (
                <EmptyState
                  icon="tasks"
                  title="No task activity yet"
                  description="Create your first task or run an offline demo to populate this chart."
                  action={
                    <Link to="/app/tasks/new" className="btn btn-primary btn-sm">
                      Create a task
                    </Link>
                  }
                />
              ) : (
                <div className="activity-chart" role="img" aria-label="Tasks created per day">
                  {data.daily.map((entry) => (
                    <div key={entry.day} className="activity-column" title={`${entry.day}: ${entry.count}`}>
                      <div className="activity-bar-wrap">
                        <div
                          className="activity-bar"
                          style={{
                            height: `${Math.max(4, (entry.count / maxDaily) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="activity-label">{entry.day.slice(5)}</span>
                      <span className="activity-count">{entry.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card
              title="Quick actions"
              subtitle="Explicit, server-enforced operations"
              className="quick-actions-card"
            >
              <div className="quick-actions">
                <Link to="/app/tasks/new" className="quick-action">
                  <span className="quick-action-icon">
                    <Icon name="plus" size={18} />
                  </span>
                  <span>
                    <strong>Create a task</strong>
                    <small>Choose autonomy, provider, budget, and criteria.</small>
                  </span>
                  <Icon name="chevron-right" size={16} />
                </Link>
                <Link to="/app/approvals" className="quick-action">
                  <span className="quick-action-icon">
                    <Icon name="shield" size={18} />
                  </span>
                  <span>
                    <strong>Review approvals</strong>
                    <small>Approve or reject gated actions with a note.</small>
                  </span>
                  <Icon name="chevron-right" size={16} />
                </Link>
                <Link to="/app/evidence" className="quick-action">
                  <span className="quick-action-icon">
                    <Icon name="evidence" size={18} />
                  </span>
                  <span>
                    <strong>Inspect evidence</strong>
                    <small>Content-addressed outputs, checks, and gate decisions.</small>
                  </span>
                  <Icon name="chevron-right" size={16} />
                </Link>
                <Link to="/app/system" className="quick-action">
                  <span className="quick-action-icon">
                    <Icon name="system" size={18} />
                  </span>
                  <span>
                    <strong>System diagnostics</strong>
                    <small>Database integrity, runtime, and provider status.</small>
                  </span>
                  <Icon name="chevron-right" size={16} />
                </Link>
              </div>
            </Card>
          </div>

          <div className="dashboard-grid dashboard-grid-lower">
            <Card
              title="Recent tasks"
              subtitle="Newest task records"
              actions={
                <Link to="/app/tasks" className="btn btn-xs btn-ghost">
                  View all <Icon name="arrow-right" size={13} />
                </Link>
              }
              padded={false}
            >
              {data.recent_tasks.length === 0 ? (
                <div className="card-body">
                  <EmptyState
                    icon="tasks"
                    title="No tasks yet"
                    description="The dashboard will show real task records here."
                  />
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Task</th>
                        <th>Status</th>
                        <th>Risk</th>
                        <th>Gate</th>
                        <th>Updated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_tasks.map((task) => (
                        <tr key={task.id}>
                          <td>
                            <Link to={`/app/tasks/${task.id}`} className="table-title">
                              {task.title}
                            </Link>
                            <span className="table-subtitle">
                              {task.provider} / {task.model}
                            </span>
                          </td>
                          <td>
                            <StatusBadge status={task.status} />
                          </td>
                          <td>
                            <Badge tone={task.risk_class === 'high' ? 'danger' : task.risk_class === 'med' ? 'warn' : 'success'}>
                              {titleCase(task.risk_class)}
                            </Badge>
                          </td>
                          <td>
                            <GateBadge decision={task.gate_decision} />
                          </td>
                          <td className="nowrap muted">{relativeTime(task.updated_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card
              title="Pending approvals"
              subtitle={
                approvals.data
                  ? `${approvals.data.total} pending`
                  : 'Checking approval queue'
              }
              actions={
                <Link to="/app/approvals" className="btn btn-xs btn-ghost">
                  Open queue <Icon name="arrow-right" size={13} />
                </Link>
              }
            >
              {approvals.loading && !approvals.data ? <SkeletonRows rows={3} /> : null}
              {approvals.error ? <ErrorState message={approvals.error} onRetry={approvals.reload} /> : null}
              {approvals.data && approvals.data.items.length === 0 ? (
                <EmptyState
                  icon="check"
                  title="Queue is clear"
                  description="No task is waiting for a human decision."
                />
              ) : null}
              {approvals.data && approvals.data.items.length > 0 ? (
                <ul className="approval-mini-list">
                  {approvals.data.items.map((approval) => (
                    <li key={approval.id}>
                      <div>
                        <Link to={`/app/tasks/${approval.task_id}`}>{approval.title ?? 'Task'}</Link>
                        <small>{approval.reason}</small>
                      </div>
                      <Badge tone="warn">{relativeTime(approval.requested_at)}</Badge>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Card>
          </div>

          <Card title="Recent audit activity" subtitle="Newest server-side events">
            {data.recent_events.length === 0 ? (
              <EmptyState icon="audit" title="No audit events yet" />
            ) : (
              <ul className="event-feed">
                {data.recent_events.map((event) => (
                  <li key={event.id}>
                    <span className="event-dot" />
                    <div className="event-feed-body">
                      <div>
                        <strong>{titleCase(event.event_type)}</strong>
                        {event.task_id ? (
                          <Link to={`/app/tasks/${event.task_id}`} className="event-task-link">
                            {event.task_id.slice(0, 8)}
                          </Link>
                        ) : null}
                      </div>
                      <span className="muted">{relativeTime(event.timestamp)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      ) : null}
    </>
  );
}

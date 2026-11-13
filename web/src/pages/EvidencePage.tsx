import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { formatNumber, relativeTime, shortId, titleCase, truncate } from '../lib/format';
import { useApi } from '../lib/useApi';
import { EvidenceViewer } from '../components/EvidenceViewer';
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

const KINDS = [
  ['', 'All kinds'],
  ['provider_output', 'Provider output'],
  ['deterministic_verification', 'Deterministic verification'],
  ['independent_verifier', 'Independent verifier'],
  ['gate_decision', 'Gate decision'],
] as const;

export function EvidencePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const kind = searchParams.get('kind') ?? '';
  const status = searchParams.get('status') ?? '';
  const search = searchParams.get('q') ?? '';
  const taskId = searchParams.get('task') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const [searchDraft, setSearchDraft] = useState(search);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);

  useEffect(() => {
    setSearchDraft(search);
  }, [search]);

  const evidence = useApi(
    () =>
      api.evidence.list({
        kind: kind || undefined,
        status: status || undefined,
        search: search || undefined,
        task_id: taskId || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [kind, status, search, taskId, offset],
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
        title="Evidence ledger"
        description="Content-addressed records produced during execution: provider output, deterministic checks, verifier results, and gate decisions. Hashes prove integrity, not truth."
      />

      <div className="toolbar toolbar-wrap">
        <div className="toolbar-filters">
          <label className="field-inline">
            <span>Kind</span>
            <select
              className="select select-sm"
              value={kind}
              onChange={(event) => updateParam('kind', event.target.value)}
            >
              {KINDS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            <span>Status</span>
            <select
              className="select select-sm"
              value={status}
              onChange={(event) => updateParam('status', event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="passed">Passed</option>
              <option value="failed">Failed</option>
              <option value="informational">Informational</option>
              <option value="ACCEPT">ACCEPT</option>
              <option value="ABSTAIN">ABSTAIN</option>
              <option value="REJECT">REJECT</option>
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
            placeholder="Search content or source"
            aria-label="Search evidence"
          />
          <button type="submit" className="btn btn-outline btn-sm">
            Search
          </button>
        </form>
      </div>

      {taskId ? (
        <div className="filter-banner">
          <span>
            Showing evidence for task <code className="inline-code">{shortId(taskId)}</code>
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

      {evidence.error ? <ErrorState message={evidence.error} onRetry={evidence.reload} /> : null}
      {evidence.loading && !evidence.data ? <SkeletonRows rows={8} /> : null}

      {evidence.data ? (
        <div className="card">
          <div className="card-body card-body-flush">
            {evidence.data.items.length === 0 ? (
              <EmptyState
                icon="evidence"
                title="No matching evidence"
                description="Evidence is recorded when a task executes. Run an offline demo to populate the ledger."
                action={
                  <Link to="/app/demos" className="btn btn-primary btn-sm">
                    Run an offline demo
                  </Link>
                }
              />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Kind</th>
                      <th>Task</th>
                      <th>Source</th>
                      <th>Status</th>
                      <th>Independent</th>
                      <th>Preview</th>
                      <th>Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.data.items.map((item) => (
                      <tr
                        key={item.id}
                        className="clickable-row"
                        onClick={() => setEvidenceId(item.id)}
                      >
                        <td>
                          <strong>{titleCase(item.kind)}</strong>
                          <span className="table-subtitle mono">{item.content_hash.slice(0, 12)}…</span>
                        </td>
                        <td>
                          <Link
                            to={`/app/tasks/${item.task_id}`}
                            className="inline-code"
                            onClick={(event) => event.stopPropagation()}
                          >
                            {shortId(item.task_id)}
                          </Link>
                        </td>
                        <td className="muted">{item.source_id || item.source_type}</td>
                        <td>
                          <Badge
                            tone={
                              item.status === 'passed' || item.status === 'ACCEPT'
                                ? 'success'
                                : item.status === 'failed' || item.status === 'REJECT'
                                  ? 'danger'
                                  : item.status === 'ABSTAIN'
                                    ? 'warn'
                                    : 'neutral'
                            }
                          >
                            {titleCase(item.status)}
                          </Badge>
                        </td>
                        <td>
                          {item.independent ? (
                            <Badge tone="success">Yes</Badge>
                          ) : (
                            <span className="muted">No</span>
                          )}
                        </td>
                        <td className="evidence-preview-cell">
                          <span className="muted">{truncate(item.content_preview || '—', 80)}</span>
                        </td>
                        <td className="muted nowrap">{relativeTime(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {evidence.data.items.length > 0 ? (
            <div className="card-footer">
              <span className="muted">{formatNumber(evidence.data.total)} evidence record(s)</span>
              <Pagination
                total={evidence.data.total}
                limit={evidence.data.limit}
                offset={evidence.data.offset}
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

      <EvidenceViewer evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </>
  );
}

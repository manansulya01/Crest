import { api } from '../lib/api';
import { formatDateTime, titleCase } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Modal } from './Modal';
import { Badge, CopyButton, ErrorState, LoadingBlock } from './UI';

export function EvidenceViewer({
  evidenceId,
  onClose,
}: {
  evidenceId: string | null;
  onClose: () => void;
}) {
  const { data, error, loading, reload } = useApi(
    () => api.evidence.get(evidenceId as string),
    [evidenceId],
    { enabled: Boolean(evidenceId) },
  );

  return (
    <Modal
      open={Boolean(evidenceId)}
      title={data ? `Evidence · ${titleCase(data.kind)}` : 'Evidence'}
      subtitle={data ? `Recorded ${formatDateTime(data.created_at)}` : undefined}
      onClose={onClose}
      wide
      footer={
        data ? (
          <>
            <CopyButton value={data.content_hash} label="Copy SHA-256" />
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Close
            </button>
          </>
        ) : null
      }
    >
      {loading ? <LoadingBlock label="Loading evidence…" /> : null}
      {error ? <ErrorState message={error} onRetry={reload} /> : null}
      {data ? (
        <div className="evidence-detail">
          <div className="evidence-meta">
            <Badge tone={data.independent ? 'success' : 'neutral'}>
              {data.independent ? 'Independent source' : 'Not independent'}
            </Badge>
            <Badge tone="info">{titleCase(data.status)}</Badge>
            <Badge tone="neutral">{data.source_type}</Badge>
          </div>
          <dl className="meta-list compact">
            <div className="meta-row">
              <dt>Source</dt>
              <dd>{data.source_id || '—'}</dd>
            </div>
            <div className="meta-row">
              <dt>Execution</dt>
              <dd className="mono">{data.execution_id ?? '—'}</dd>
            </div>
            <div className="meta-row">
              <dt>Content hash</dt>
              <dd className="mono hash-value">{data.content_hash}</dd>
            </div>
          </dl>
          <h3 className="subsection-title">Content</h3>
          <pre className="code-panel evidence-content">{data.content ?? data.content_preview}</pre>
          <h3 className="subsection-title">Provenance</h3>
          <pre className="code-panel">{JSON.stringify(data.provenance, null, 2)}</pre>
        </div>
      ) : null}
    </Modal>
  );
}

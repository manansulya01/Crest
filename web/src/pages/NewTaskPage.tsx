import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { unwrapExecution } from '../lib/types';
import type { TaskPayload } from '../lib/types';
import { useApi } from '../lib/useApi';
import { useToast } from '../lib/toast';
import { Icon } from '../components/Icons';
import { TaskForm } from '../components/TaskForm';
import { Card, ErrorState, InlineNotice, LoadingBlock, PageHeader } from '../components/UI';

export function NewTaskPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const settings = useApi(() => api.settings.get(), []);
  const providers = useApi(() => api.providers.list(), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(payload: TaskPayload, executeNow: boolean) {
    setBusy(true);
    setError(null);
    try {
      const task = await api.tasks.create(payload);
      if (executeNow) {
        try {
          const response = await api.tasks.execute(task.id);
          const updated = unwrapExecution(response);
          if (updated.status === 'awaiting_approval') {
            notify('Task created and is awaiting approval.', 'info');
          } else {
            notify('Task created and execution started.', 'success');
          }
        } catch (caught) {
          notify(
            caught instanceof Error ? caught.message : 'Execution could not be started.',
            'error',
          );
        }
      } else {
        notify('Task created. Run it when you are ready.', 'success');
      }
      navigate(`/app/tasks/${task.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  const loading = settings.loading || providers.loading;
  const loadError = settings.error || providers.error;

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="New task"
        description="Define the outcome, the authority the agent may use, and the evidence required before acceptance."
        actions={
          <Link to="/app/tasks" className="btn btn-outline btn-sm">
            Back to tasks
          </Link>
        }
      />

      {loading && !settings.data ? <LoadingBlock label="Loading settings and providers…" /> : null}
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
        <InlineNotice tone="danger" title="Task could not be created" icon="alert">
          {error}
        </InlineNotice>
      ) : null}

      {settings.data && providers.data ? (
        <Card>
          <TaskForm
            mode="create"
            settings={settings.data}
            providers={providers.data}
            busy={busy}
            submitLabel="Create task"
            allowExecuteNow
            onSubmit={handleSubmit}
          />
        </Card>
      ) : null}

      <div className="page-note">
        <Icon name="lock" size={15} />
        <span>
          The frontend is not the authority. Every execution re-checks autonomy, provider access,
          budgets, approvals, and verification on the server.
        </span>
      </div>
    </>
  );
}

import type {
  Approval,
  AuditEvent,
  AutonomyResponse,
  BudgetSummary,
  Diagnostics,
  Evidence,
  ExecuteResponse,
  ModelInfo,
  Paginated,
  Plan,
  Provider,
  RoutingResponse,
  RoutingRule,
  Settings,
  Stats,
  Task,
  TaskPayload,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';
const TOKEN_KEY = 'crest.api_token';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
}

export function setToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable in hardened browser contexts; the API still
    // works when no token is configured server-side.
  }
}

function buildHeaders(hasBody: boolean): Headers {
  const headers = new Headers();
  if (hasBody) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (body?.detail) return JSON.stringify(body.detail);
    return response.statusText;
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: buildHeaders(Boolean(init?.body)),
    });
  } catch {
    throw new ApiError(
      0,
      'Cannot reach the CREST API. Start it with: python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000',
    );
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue;
    search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : '';
}

async function download(path: string, filename: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: buildHeaders(false) });
  } catch {
    throw new ApiError(0, 'Cannot reach the CREST API to download this file.');
  }
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const api = {
  health: () =>
    request<{ status: string; version: string; timestamp: string; database: string }>(
      '/api/v1/health',
    ),

  diagnostics: () => request<Diagnostics>('/api/v1/diagnostics'),

  systemInfo: () => request<Record<string, unknown>>('/api/v1/system/info'),

  tasks: {
    list: (params: {
      status?: string;
      risk_class?: string;
      search?: string;
      limit?: number;
      offset?: number;
    } = {}) => request<Paginated<Task>>(`/api/v1/tasks${query(params)}`),
    get: (id: string) => request<Task>(`/api/v1/tasks/${id}`),
    create: (payload: TaskPayload) =>
      request<Task>('/api/v1/tasks', { method: 'POST', body: JSON.stringify(payload) }),
    update: (id: string, payload: Partial<TaskPayload>) =>
      request<Task>(`/api/v1/tasks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    remove: (id: string) =>
      request<{ id: string; deleted: boolean }>(`/api/v1/tasks/${id}`, { method: 'DELETE' }),
    plan: (id: string) => request<Plan>(`/api/v1/tasks/${id}/plan`, { method: 'POST' }),
    execute: (id: string, wait = false) =>
      request<ExecuteResponse>(`/api/v1/tasks/${id}/execute${query({ wait })}`, {
        method: 'POST',
      }),
    approve: (
      id: string,
      payload: { decision: 'approve' | 'reject'; note?: string; start_execution?: boolean; wait?: boolean },
    ) =>
      request<Task>(`/api/v1/tasks/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    cancel: (id: string) => request<Task>(`/api/v1/tasks/${id}/cancel`, { method: 'POST' }),
    events: (id: string, limit = 500) =>
      request<Paginated<AuditEvent>>(`/api/v1/tasks/${id}/events${query({ limit })}`),
    evidence: (id: string, limit = 200) =>
      request<Paginated<Evidence>>(`/api/v1/tasks/${id}/evidence${query({ limit })}`),
    report: (id: string) =>
      download(`/api/v1/tasks/${id}/report`, `crest-task-${id.slice(0, 8)}.json`),
  },

  providers: {
    list: () => request<Provider[]>('/api/v1/providers'),
    update: (id: string, payload: Partial<Provider>) =>
      request<Provider>(`/api/v1/providers/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    test: (id: string, model?: string) =>
      request<Record<string, unknown>>(`/api/v1/providers/${id}/test`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true, model }),
      }),
  },

  models: () => request<ModelInfo[]>('/api/v1/models'),

  routing: {
    get: () => request<RoutingResponse>('/api/v1/routing'),
    update: (rules: RoutingRule[], fallbackEnabled: boolean) =>
      request<RoutingResponse>('/api/v1/routing', {
        method: 'PUT',
        body: JSON.stringify({ rules, fallback_enabled: fallbackEnabled }),
      }),
  },

  settings: {
    get: () => request<Settings>('/api/v1/settings'),
    update: (payload: Partial<Settings>) =>
      request<Settings>('/api/v1/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
  },

  autonomy: () => request<AutonomyResponse>('/api/v1/autonomy/levels'),

  audit: (params: {
    task_id?: string;
    event_type?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}) => request<Paginated<AuditEvent>>(`/api/v1/audit${query(params)}`),

  evidence: {
    list: (params: {
      task_id?: string;
      kind?: string;
      status?: string;
      search?: string;
      limit?: number;
      offset?: number;
    } = {}) => request<Paginated<Evidence>>(`/api/v1/evidence${query(params)}`),
    get: (id: string) => request<Evidence>(`/api/v1/evidence/${id}`),
  },

  approvals: (params: { status?: string; limit?: number; offset?: number } = {}) =>
    request<Paginated<Approval>>(`/api/v1/approvals${query(params)}`),

  stats: () => request<Stats>('/api/v1/stats/overview'),

  budgets: () => request<BudgetSummary>('/api/v1/budgets/summary'),

  exportBackup: () => download('/api/v1/export', `crest-backup-${new Date().toISOString().slice(0, 10)}.json`),

  purge: (confirm: boolean, force: boolean) =>
    request<{ purged: number; cutoff: string; retention_days: number }>(
      `/api/v1/maintenance/purge${query({ confirm, force })}`,
      { method: 'POST' },
    ),
};

export type { Task, TaskPayload };

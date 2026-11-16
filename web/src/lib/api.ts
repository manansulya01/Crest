import type {
  Approval,
  AuditEvent,
  AutonomyResponse,
  BackupList,
  BackupManifest,
  BackupRestore,
  BackupVerify,
  BudgetSummary,
  ControlStatus,
  CredentialStatus,
  Diagnostics,
  Evidence,
  ExecuteResponse,
  ImportValidation,
  LogInfo,
  ModelInfo,
  ModesResponse,
  OperatingModeId,
  Paginated,
  Plan,
  Provider,
  ProviderUsage,
  RoutingResponse,
  RoutingRule,
  Settings,
  Stats,
  SystemInfo,
  Task,
  TaskPayload,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';
const TOKEN_KEY = 'crest.api_token';
const CSRF_HEADER = 'X-Crest-CSRF';
let csrfToken = '';

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

const STATE_CHANGING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function buildHeaders(hasBody: boolean, method = 'GET'): Headers {
  const headers = new Headers();
  if (hasBody) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // Browser requests carry an Origin header and must present the per-process
  // CSRF token. Non-browser clients do not send Origin and are unaffected.
  if (csrfToken && STATE_CHANGING.has(method.toUpperCase())) {
    headers.set(CSRF_HEADER, csrfToken);
  }
  return headers;
}

async function fetchCsrf(): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/security/csrf`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  const body = (await response.json()) as { token: string };
  csrfToken = body.token;
  return csrfToken;
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

async function send(path: string, init: RequestInit | undefined, method: string): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers: buildHeaders(Boolean(init?.body), method),
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase();
  let response: Response;
  try {
    // Ensure we have a CSRF token before the first state-changing request.
    if (STATE_CHANGING.has(method) && !csrfToken) await fetchCsrf();
    response = await send(path, init, method);
    // Token may have rotated (server restart) — refresh once and retry.
    if (response.status === 403 && STATE_CHANGING.has(method)) {
      const detail = await response.clone().text();
      if (detail.toLowerCase().includes('csrf')) {
        csrfToken = '';
        await fetchCsrf();
        response = await send(path, init, method);
      }
    }
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw new ApiError(
      0,
      'Cannot reach the CREST API. Start the CREST desktop app or the local backend service.',
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
    request<{
      status: string;
      version: string;
      timestamp: string;
      database: string;
      schema_version: number;
      operating_mode: OperatingModeId;
      paused: boolean;
      control: ControlStatus;
    }>('/api/v1/health'),

  diagnostics: () => request<Diagnostics>('/api/v1/diagnostics'),

  systemInfo: () => request<SystemInfo>('/api/v1/system/info'),

  // ----------------------------------------------------------- security/CSRF
  security: {
    csrf: () => fetchCsrf(),
  },

  // ---------------------------------------------------------------- controls
  control: {
    status: () => request<ControlStatus>('/api/v1/control'),
    pause: () => request<ControlStatus>('/api/v1/control/pause', { method: 'POST' }),
    resume: () => request<ControlStatus>('/api/v1/control/resume', { method: 'POST' }),
    stopAll: () =>
      request<{ cancelled: number; task_ids: string[]; errors: Array<{ task_id: string; error: string }> }>(
        '/api/v1/control/stop-all',
        { method: 'POST' },
      ),
  },

  // ------------------------------------------------------------------- modes
  modes: {
    get: () => request<ModesResponse>('/api/v1/modes'),
    set: (mode: OperatingModeId) =>
      request<{ operating_mode: OperatingModeId; previous: OperatingModeId }>('/api/v1/modes', {
        method: 'PUT',
        body: JSON.stringify({ mode }),
      }),
  },

  // ------------------------------------------------------------- credentials
  credentials: {
    status: () => request<CredentialStatus>('/api/v1/credentials'),
    set: (providerId: string, apiKey: string) =>
      request<{ provider_id: string; configured: boolean; storage: string; updated_at: string }>(
        `/api/v1/credentials/${providerId}`,
        { method: 'PUT', body: JSON.stringify({ api_key: apiKey, confirm: true }) },
      ),
    clear: (providerId: string) =>
      request<{ provider_id: string; configured: boolean; removed: boolean }>(
        `/api/v1/credentials/${providerId}`,
        { method: 'DELETE' },
      ),
  },

  // ----------------------------------------------------------------- backups
  backups: {
    list: () => request<BackupList>('/api/v1/backups'),
    create: (note = '') =>
      request<BackupManifest>('/api/v1/backups', {
        method: 'POST',
        body: JSON.stringify({ note }),
      }),
    verify: (name: string) =>
      request<BackupVerify>('/api/v1/backups/verify', {
        method: 'POST',
        body: JSON.stringify({ name }),
      }),
    restore: (name: string) =>
      request<BackupRestore>('/api/v1/backups/restore', {
        method: 'POST',
        body: JSON.stringify({ name, confirm: true }),
      }),
    download: (name: string) =>
      download(`/api/v1/backups/${encodeURIComponent(name)}/download`, `crest-db-${name}`),
  },

  // -------------------------------------------------------------- logs/import
  logs: (lines = 200) => request<LogInfo>(`/api/v1/logs${query({ lines })}`),
  validateImport: (payload: unknown) =>
    request<ImportValidation>('/api/v1/import/validate', {
      method: 'POST',
      body: JSON.stringify({ payload }),
    }),

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
    usage: (id: string, limit = 100) =>
      request<ProviderUsage>(`/api/v1/providers/${id}/usage${query({ limit })}`),
    discoverModels: (id: string) =>
      request<{ provider: string; models: string[]; count: number }>(
        `/api/v1/providers/${id}/models/discover`,
        { method: 'POST', body: JSON.stringify({ confirm: true }) },
      ),
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

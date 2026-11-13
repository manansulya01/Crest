export type RiskClass = 'low' | 'med' | 'high';
export type OutputFormat = 'text' | 'json';
export type DemoScenario = 'verification_failure' | 'recovery' | 'approval_required';

export interface Task {
  id: string;
  title: string;
  description: string;
  risk_class: RiskClass;
  autonomy_level: number;
  status: string;
  provider: string | null;
  model: string | null;
  budget: number;
  token_budget: number;
  timeout_seconds: number;
  acceptance_criteria: string[];
  output_format: OutputFormat;
  demo_scenario: DemoScenario | null;
  custom_policy: Record<string, unknown> | null;
  result?: string | null;
  result_preview?: string;
  result_hash: string | null;
  verification_status: string | null;
  gate_decision: string | null;
  gate_reason: string | null;
  cost: number;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  deleted_at: string | null;
  provider_name?: string | null;
  provider_kind?: string | null;
  is_mock?: boolean;
  budget_remaining?: number;
  token_remaining?: number;
  policy_fingerprint?: string;
  plan?: Plan | null;
  executions?: Execution[];
  evidence?: Evidence[];
  approvals?: Approval[];
  events?: AuditEvent[];
}

export interface PlanStep {
  id: string;
  name: string;
  action: string;
  description: string;
}

export interface Plan {
  id: string;
  task_id: string;
  version: number;
  steps: PlanStep[];
  created_at: string;
  route_reason?: string;
  provider?: string;
  model?: string;
}

export interface ExecutionStep {
  id: number;
  execution_id: string;
  seq: number;
  name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  detail: Record<string, unknown>;
}

export interface Execution {
  id: string;
  task_id: string;
  status: string;
  attempt: number;
  provider: string | null;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
  cost: number;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  cancel_requested: number;
  detail: Record<string, unknown>;
  steps: ExecutionStep[];
}

export interface Evidence {
  id: string;
  task_id: string;
  execution_id: string | null;
  kind: string;
  source_type: string;
  source_id: string;
  independent: boolean;
  status: string;
  content?: string;
  content_preview: string;
  content_hash: string;
  provenance: Record<string, unknown>;
  created_at: string;
}

export interface Approval {
  id: string;
  task_id: string;
  execution_id: string | null;
  action: string;
  status: string;
  reason: string;
  note: string;
  policy_fingerprint: string;
  requested_at: string;
  decided_at: string | null;
  consumed_at: string | null;
  title?: string;
  risk_class?: RiskClass;
  autonomy_level?: number;
  task_status?: string;
  provider?: string | null;
  model?: string | null;
}

export interface AuditEvent {
  id: number;
  task_id: string | null;
  execution_id: string | null;
  event_type: string;
  actor: string;
  detail: Record<string, unknown>;
  timestamp: string;
}

export interface Provider {
  id: string;
  kind: string;
  name: string;
  enabled: boolean;
  external: boolean;
  base_url: string;
  api_key_env: string;
  key_present: boolean;
  default_model: string;
  models: string[];
  input_cost_per_1k: number;
  output_cost_per_1k: number;
  max_output_tokens: number;
  timeout_seconds: number;
  status: 'ready' | 'disabled' | 'key_missing';
  last_test_status: string | null;
  last_test_at: string | null;
  last_test_detail: string | null;
  cost_configured: boolean;
}

export interface ModelInfo {
  id: string;
  model: string;
  name: string;
  provider: string;
  provider_name: string;
  provider_kind: string;
  available: boolean;
  external: boolean;
  cost_configured: boolean;
  input_cost_per_1k: number;
  output_cost_per_1k: number;
}

export interface Settings {
  default_autonomy_level: number;
  max_autonomy_level: number;
  default_risk_class: RiskClass;
  default_budget: number;
  max_task_budget: number;
  default_token_budget: number;
  max_token_budget: number;
  default_timeout_seconds: number;
  max_execution_seconds: number;
  default_provider: string;
  default_model: string;
  allow_external_calls: boolean;
  require_approval_high_risk: boolean;
  require_approval_external: boolean;
  allow_custom_policies: boolean;
  max_recovery_attempts: number;
  verification_mode: 'deterministic' | 'provider';
  verifier_provider: string;
  verifier_model: string;
  routing_fallback_enabled: boolean;
  retention_enabled: boolean;
  retention_days: number;
}

export interface AutonomyLevel {
  level: number;
  name: string;
  summary: string;
  can_execute: boolean;
  default_actions: string[];
  approval: string;
  enabled?: boolean;
  global_high_risk_approval?: boolean;
  global_external_approval?: boolean;
  external_calls_enabled?: boolean;
}

export interface AutonomyResponse {
  levels: AutonomyLevel[];
  matrix: AutonomyLevel[];
  settings: Settings;
}

export interface RoutingRule {
  id?: number;
  priority: number;
  risk_class: RiskClass | '*';
  provider: string;
  model: string;
  enabled: boolean;
}

export interface RoutingResponse {
  rules: RoutingRule[];
  fallback_enabled: boolean;
}

export interface Stats {
  total_tasks: number;
  status_counts: Record<string, number>;
  risk_counts: Record<string, number>;
  gate_counts: Record<string, number>;
  active_executions: number;
  completed: number;
  failed: number;
  abstained: number;
  awaiting_approval: number;
  verification_passed: number;
  verification_failed: number;
  verification_pass_rate: number | null;
  completion_rate: number | null;
  budget_used: number;
  input_tokens: number;
  output_tokens: number;
  daily: Array<{ day: string; count: number }>;
  recent_events: AuditEvent[];
  recent_tasks: Task[];
}

export interface Diagnostics {
  status: string;
  version: string;
  started_at: string;
  uptime_seconds: number;
  python: string;
  platform: string;
  data_dir: string;
  database: {
    path: string;
    size_bytes: number;
    integrity: { ok: boolean; result: string[] };
    counts: Record<string, number>;
  };
  frontend_built: boolean;
  auth_token_required: boolean;
  external_calls_enabled: boolean;
  providers: Provider[];
  settings: Record<string, unknown>;
}

export interface BudgetSummary {
  limits: {
    max_task_budget: number;
    max_token_budget: number;
    max_execution_seconds: number;
    default_budget: number;
    default_token_budget: number;
  };
  totals: {
    cost: number;
    input_tokens: number;
    output_tokens: number;
    tokens: number;
    tasks: number;
  };
  tasks: Array<{
    id: string;
    title: string;
    status: string;
    budget: number;
    cost: number;
    token_budget: number;
    tokens: number;
    provider: string | null;
    model: string | null;
  }>;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface TaskPayload {
  title: string;
  description?: string;
  risk_class?: RiskClass;
  autonomy_level?: number;
  provider?: string | null;
  model?: string | null;
  budget?: number;
  token_budget?: number;
  timeout_seconds?: number;
  acceptance_criteria?: string[];
  output_format?: OutputFormat;
  demo_scenario?: DemoScenario | null;
  custom_policy?: Record<string, unknown> | null;
  idempotency_key?: string;
}

export interface ExecuteAwaiting {
  task: Task;
  approval: Approval;
  status: 'awaiting_approval';
}

export type ExecuteResponse = Task | ExecuteAwaiting;

export function unwrapExecution(response: ExecuteResponse): Task {
  if ('task' in response) return response.task;
  return response;
}

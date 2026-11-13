export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['week', 60 * 60 * 24 * 7],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
    ['second', 1],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size || unit === 'second') {
      return formatter.format(Math.round(seconds / size), unit);
    }
  }
  return 'just now';
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat().format(value);
}

export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value === 0) return '$0.00';
  if (Math.abs(value) < 0.01) return `$${value.toFixed(6)}`;
  return `$${value.toFixed(2)}`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function shortId(value: string | null | undefined, length = 8): string {
  if (!value) return '—';
  return value.slice(0, length);
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return '—';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function truncate(value: string, length = 140): string {
  if (value.length <= length) return value;
  return `${value.slice(0, length).trimEnd()}…`;
}

export function jsonPreview(value: unknown, length = 140): string {
  try {
    return truncate(JSON.stringify(value, null, 2), length);
  } catch {
    return String(value);
  }
}

export function statusTone(status: string | null | undefined): string {
  switch (status) {
    case 'completed':
    case 'passed':
    case 'ready':
    case 'ok':
    case 'ACCEPT':
    case 'approved':
      return 'success';
    case 'failed':
    case 'denied':
    case 'rejected':
    case 'REJECT':
    case 'error':
      return 'danger';
    case 'abstained':
    case 'awaiting_approval':
    case 'budget_exhausted':
    case 'interrupted':
    case 'timed_out':
    case 'ABSTAIN':
    case 'key_missing':
      return 'warn';
    case 'queued':
    case 'running':
    case 'pending':
      return 'info';
    default:
      return 'neutral';
  }
}

export function riskTone(risk: string | null | undefined): string {
  if (risk === 'high') return 'danger';
  if (risk === 'med') return 'warn';
  if (risk === 'low') return 'success';
  return 'neutral';
}

export function gateTone(decision: string | null | undefined): string {
  if (decision === 'ACCEPT') return 'success';
  if (decision === 'ABSTAIN') return 'warn';
  if (decision === 'REJECT') return 'danger';
  return 'neutral';
}

export function isActiveStatus(status: string | null | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'awaiting_approval';
}

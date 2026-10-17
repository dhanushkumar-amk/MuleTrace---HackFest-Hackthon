/**
 * Indian rupee and time formatters with tabular alignment support.
 */

export function formatRupees(amount: number | null | undefined, prefix: '₹' | 'Rs ' = '₹'): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return `${prefix}0`;
  }
  const formatted = new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 0,
  }).format(amount);
  return `${prefix}${formatted}`;
}

export function formatCompactRupees(amount: number): string {
  if (amount >= 10000000) {
    return `₹${(amount / 10000000).toFixed(1)} Cr`;
  }
  if (amount >= 100000) {
    return `₹${(amount / 100000).toFixed(1)} L`;
  }
  if (amount >= 1000) {
    return `₹${(amount / 1000).toFixed(1)}K`;
  }
  return `₹${amount}`;
}

export function formatExactIST(unixTimestamp: number): string {
  if (!unixTimestamp) return '—';
  // If timestamp is in seconds, convert to ms
  const ms = unixTimestamp < 10000000000 ? unixTimestamp * 1000 : unixTimestamp;
  const date = new Date(ms);
  return date.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' IST';
}

export function formatRelativeTime(unixTimestamp: number): string {
  if (!unixTimestamp) return '—';
  const ms = unixTimestamp < 10000000000 ? unixTimestamp * 1000 : unixTimestamp;
  const now = Date.now();
  const diffSec = Math.floor((now - ms) / 1000);

  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  return `${diffDays}d ago`;
}

export function formatElapsedOffset(baseTimestamp: number, currentTimestamp: number): string {
  const diffSec = Math.max(0, currentTimestamp - baseTimestamp);
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  if (min === 0) {
    return `+${sec}s`;
  }
  return `+${min}m ${sec}s`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatAccountShort(account: string): string {
  if (!account) return '';
  return account.replace(/^ACC_/, '');
}

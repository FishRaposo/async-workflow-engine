// Shared status -> style mapping for run and step statuses, plus small
// formatting helpers used across pages.

export interface StatusStyle {
  /** Tailwind classes for a pill/badge. */
  badge: string;
  /** Hex fill used for the DAG node + recharts segments. */
  color: string;
  /** Human label. */
  label: string;
}

const STEP: Record<string, StatusStyle> = {
  COMPLETED: { badge: "bg-emerald-100 text-emerald-700 border border-emerald-200", color: "#10b981", label: "Completed" },
  FAILED: { badge: "bg-rose-100 text-rose-700 border border-rose-200", color: "#ef4444", label: "Failed" },
  RUNNING: { badge: "bg-sky-100 text-sky-700 border border-sky-200", color: "#0ea5e9", label: "Running" },
  SKIPPED: { badge: "bg-amber-100 text-amber-700 border border-amber-200", color: "#f59e0b", label: "Skipped" },
  PENDING: { badge: "bg-gray-100 text-gray-600 border border-gray-200", color: "#9ca3af", label: "Pending" },
};

const RUN: Record<string, StatusStyle> = {
  completed: { badge: "bg-emerald-100 text-emerald-700 border border-emerald-200", color: "#10b981", label: "Completed" },
  failed: { badge: "bg-rose-100 text-rose-700 border border-rose-200", color: "#ef4444", label: "Failed" },
  partial: { badge: "bg-amber-100 text-amber-700 border border-amber-200", color: "#f59e0b", label: "Partial" },
  pending: { badge: "bg-gray-100 text-gray-600 border border-gray-200", color: "#9ca3af", label: "Pending" },
};

const FALLBACK: StatusStyle = {
  badge: "bg-gray-100 text-gray-600 border border-gray-200",
  color: "#9ca3af",
  label: "Unknown",
};

export function stepStatusStyle(status: string): StatusStyle {
  return STEP[status?.toUpperCase()] ?? { ...FALLBACK, label: status || "Unknown" };
}

export function runStatusStyle(status: string): StatusStyle {
  return RUN[status?.toLowerCase()] ?? { ...FALLBACK, label: status || "Unknown" };
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const diffMs = Date.now() - d.getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

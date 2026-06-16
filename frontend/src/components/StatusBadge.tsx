import { runStatusStyle, stepStatusStyle } from "@/lib/status";

interface Props {
  status: string;
  /** "run" maps lowercase run statuses, "step" maps uppercase step statuses. */
  kind?: "run" | "step";
  className?: string;
}

export default function StatusBadge({ status, kind = "run", className = "" }: Props) {
  const style = kind === "step" ? stepStatusStyle(status) : runStatusStyle(status);
  return (
    <span
      data-testid="status-badge"
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${style.badge} ${className}`}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: style.color }}
        aria-hidden
      />
      {style.label}
    </span>
  );
}

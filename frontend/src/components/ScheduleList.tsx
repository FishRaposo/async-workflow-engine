import { CalendarClock, Trash2 } from "lucide-react";
import type { Schedule } from "@/types";
import { formatDate } from "@/lib/status";

interface Props {
  schedules: Schedule[];
  onDelete?: (name: string) => void;
  deletingName?: string | null;
}

export default function ScheduleList({ schedules, onDelete, deletingName }: Props) {
  return (
    <ul data-testid="schedule-list" className="space-y-3">
      {schedules.map((s) => (
        <li
          key={s.name}
          className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-brand-500" />
              <span className="font-semibold text-gray-900">{s.name}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  s.enabled
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {s.enabled ? "enabled" : "disabled"}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs text-gray-500">{s.cron}</p>
            <p className="mt-1 text-xs text-gray-400">
              Last run {formatDate(s.last_run)} · Next run{" "}
              {formatDate(s.next_run)}
            </p>
          </div>
          {onDelete && (
            <button
              onClick={() => onDelete(s.name)}
              disabled={deletingName === s.name}
              className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-rose-50 hover:text-rose-500 disabled:opacity-50"
              title={`Delete ${s.name}`}
              aria-label={`Delete ${s.name}`}
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { RunListItem } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import { formatDate, relativeTime } from "@/lib/status";

interface Props {
  runs: RunListItem[];
}

/** Presentational run list — pure, rendered from data (easy to unit-test). */
export default function RunList({ runs }: Props) {
  return (
    <ul data-testid="run-list" className="space-y-3">
      {runs.map((run) => (
        <li key={run.run_id}>
          <Link
            href={`/runs/${run.run_id}`}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 transition-shadow hover:shadow-md"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-semibold text-gray-900">
                  {run.workflow_name}
                </span>
                <StatusBadge status={run.status} kind="run" />
              </div>
              <p className="mt-1 truncate font-mono text-xs text-gray-400">
                {run.run_id}
              </p>
            </div>
            <div className="ml-4 flex shrink-0 items-center gap-3 text-right">
              <div>
                <p className="text-sm text-gray-700">{formatDate(run.created_at)}</p>
                <p className="text-xs text-gray-400">{relativeTime(run.created_at)}</p>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-300" />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

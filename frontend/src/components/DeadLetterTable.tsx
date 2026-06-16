import Link from "next/link";
import type { DeadLetter } from "@/types";

interface Props {
  deadLetters: DeadLetter[];
  /** Called with a run_id when the user clicks "Rerun" for that row. */
  onRerun?: (runId: string) => void;
  rerunningRunId?: string | null;
}

export default function DeadLetterTable({
  deadLetters,
  onRerun,
  rerunningRunId,
}: Props) {
  return (
    <div
      data-testid="dead-letter-table"
      className="overflow-x-auto rounded-lg border border-gray-200 bg-white"
    >
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
          <tr>
            <th className="px-4 py-3">Step</th>
            <th className="px-4 py-3">Task</th>
            <th className="px-4 py-3">Error</th>
            <th className="px-4 py-3 text-center">Attempts</th>
            <th className="px-4 py-3">Run</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {deadLetters.map((dl, i) => (
            <tr key={`${dl.run_id ?? "?"}-${dl.step_id}-${i}`}>
              <td className="px-4 py-3 font-medium text-gray-800">
                {dl.step_id}
              </td>
              <td className="px-4 py-3">
                <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-600">
                  {dl.task}
                </span>
              </td>
              <td className="max-w-xs px-4 py-3 text-rose-700">
                <span className="line-clamp-2" title={dl.error}>
                  {dl.error}
                </span>
              </td>
              <td className="px-4 py-3 text-center">
                <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-amber-100 px-2 text-xs font-semibold text-amber-700">
                  {dl.attempts}
                </span>
              </td>
              <td className="px-4 py-3">
                {dl.run_id ? (
                  <Link
                    href={`/runs/${dl.run_id}`}
                    className="font-mono text-xs text-brand-600 underline"
                  >
                    {dl.run_id.slice(0, 8)}…
                  </Link>
                ) : (
                  <span className="text-xs text-gray-400">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-right">
                {dl.run_id && onRerun && (
                  <button
                    onClick={() => onRerun(dl.run_id!)}
                    disabled={rerunningRunId === dl.run_id}
                    className="rounded-lg border border-brand-200 px-2.5 py-1 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-50 disabled:opacity-50"
                  >
                    {rerunningRunId === dl.run_id ? "Rerunning…" : "Rerun"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

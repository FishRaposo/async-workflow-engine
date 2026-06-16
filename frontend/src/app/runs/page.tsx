"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ListChecks, PlayCircle, RefreshCw } from "lucide-react";
import type { RunListItem } from "@/types";
import { apiClient } from "@/lib/api";
import RunList from "@/components/RunList";
import RunStatusChart from "@/components/RunStatusChart";
import StatusBadge from "@/components/StatusBadge";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { RunListSkeleton } from "@/components/LoadingSkeleton";

const STATUS_FILTERS = ["all", "completed", "failed", "partial"] as const;

export default function RunsPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listRuns();
      setRuns(data.runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visible =
    filter === "all"
      ? runs
      : runs.filter((r) => (r.status || "").toLowerCase() === filter);

  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    const key = (r.status || "").toLowerCase();
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ListChecks className="h-6 w-6 text-brand-600" />
            Workflow runs
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Every dispatched run, newest first. Click a run to see its DAG.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <Link href="/trigger" className="btn-primary flex items-center gap-2">
            <PlayCircle className="h-4 w-4" />
            New run
          </Link>
        </div>
      </div>

      <div className="mb-8 grid gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">
            Status summary
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(["completed", "failed", "partial", "pending"] as const).map((s) => (
              <div
                key={s}
                className="rounded-lg border border-gray-100 bg-gray-50 p-3"
              >
                <div className="text-2xl font-bold text-gray-900">
                  {counts[s] ?? 0}
                </div>
                <StatusBadge status={s} kind="run" className="mt-1" />
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h2 className="mb-1 text-sm font-semibold text-gray-700">
            Distribution
          </h2>
          <RunStatusChart runs={runs} />
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-sm font-medium capitalize transition-colors ${
              filter === f
                ? "bg-brand-600 text-white"
                : "bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50"
            }`}
          >
            {f}
            {f !== "all" && (
              <span className="ml-1.5 text-xs opacity-70">
                {counts[f] ?? 0}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <RunListSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : visible.length === 0 ? (
        <EmptyState
          title="No runs to show"
          message={
            runs.length === 0
              ? "Trigger a workflow to see it appear here."
              : "No runs match this filter."
          }
          icon={ListChecks}
          action={
            runs.length === 0 ? (
              <Link href="/trigger" className="btn-primary">
                Trigger a workflow
              </Link>
            ) : undefined
          }
        />
      ) : (
        <RunList runs={visible} />
      )}
    </div>
  );
}

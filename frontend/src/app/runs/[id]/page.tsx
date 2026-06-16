"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, RotateCcw } from "lucide-react";
import type { DagResponse, DispatchResult, RunDetail } from "@/types";
import { apiClient, ApiError } from "@/lib/api";
import { isDemoMode } from "@/lib/demoMode";
import DagGraph from "@/components/DagGraph";
import StatusBadge from "@/components/StatusBadge";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { CardSkeleton, DagSkeleton } from "@/components/LoadingSkeleton";
import { formatDate } from "@/lib/status";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [run, setRun] = useState<RunDetail | null>(null);
  const [dag, setDag] = useState<DagResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [rerunning, setRerunning] = useState(false);
  const [rerunMsg, setRerunMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [runData, dagData] = await Promise.all([
        apiClient.getRun(runId),
        apiClient.getDag(runId).catch(() => null),
      ]);
      setRun(runData);
      setDag(dagData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run.");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRerun = async () => {
    setRerunning(true);
    setRerunMsg(null);
    try {
      if (isDemoMode()) {
        setRerunMsg("Demo mode: rerun is simulated (no backend to dispatch to).");
        return;
      }
      const res: DispatchResult = await apiClient.rerunWorkflow(runId);
      setRerunMsg(
        res.dispatched === "async"
          ? `Re-dispatched asynchronously (task ${res.task_id}).`
          : `Rerun finished with status "${res.status}".`
      );
      await load();
    } catch (err) {
      setRerunMsg(
        err instanceof ApiError
          ? `Rerun failed: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Rerun failed."
      );
    } finally {
      setRerunning(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <Link
        href="/runs"
        className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to runs
      </Link>

      {loading ? (
        <div className="space-y-6">
          <CardSkeleton />
          <DagSkeleton />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !run ? (
        <EmptyState title="Run not found" message={`No run with id ${runId}.`} />
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900">
                  {run.workflow_name}
                </h1>
                <StatusBadge status={run.status} kind="run" />
              </div>
              <p className="mt-1 font-mono text-xs text-gray-400">{run.run_id}</p>
              <p className="mt-1 text-sm text-gray-500">
                Created {formatDate(run.created_at)} · Completed{" "}
                {formatDate(run.completed_at)}
              </p>
            </div>
            <button
              onClick={handleRerun}
              disabled={rerunning}
              className="btn-primary flex items-center gap-2"
            >
              <RotateCcw className={`h-4 w-4 ${rerunning ? "animate-spin" : ""}`} />
              {rerunning ? "Rerunning…" : "Rerun"}
            </button>
          </div>

          {rerunMsg && (
            <div className="mb-6 rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-700">
              {rerunMsg}
            </div>
          )}

          <section className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-gray-900">DAG</h2>
            {dag ? (
              <DagGraph dag={dag} />
            ) : (
              <EmptyState
                title="No DAG available"
                message="This run has no stored definition to project a DAG from."
              />
            )}
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="card">
              <h2 className="mb-3 text-sm font-semibold text-gray-700">Steps</h2>
              <ul className="divide-y divide-gray-100">
                {Object.entries(run.step_statuses).map(([stepId, status]) => (
                  <li
                    key={stepId}
                    className="flex items-center justify-between py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-gray-800">
                        {stepId}
                      </p>
                      {run.task_names?.[stepId] && (
                        <p className="truncate text-xs text-gray-400">
                          {run.task_names[stepId]}
                        </p>
                      )}
                    </div>
                    <StatusBadge status={status} kind="step" />
                  </li>
                ))}
              </ul>
            </div>

            <div className="card">
              <h2 className="mb-3 text-sm font-semibold text-gray-700">
                Results &amp; errors
              </h2>
              {Object.keys(run.results).length === 0 &&
              Object.keys(run.errors).length === 0 ? (
                <p className="text-sm text-gray-400">
                  No step results were captured for this run.
                </p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(run.results).map(([stepId, result]) => (
                    <div key={stepId}>
                      <p className="text-xs font-semibold text-gray-500">
                        {stepId}
                      </p>
                      <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-700">
                        {result}
                      </pre>
                    </div>
                  ))}
                  {Object.entries(run.errors).map(([stepId, err]) => (
                    <div key={stepId}>
                      <p className="text-xs font-semibold text-rose-500">
                        {stepId} — error
                      </p>
                      <pre className="mt-1 overflow-x-auto rounded bg-rose-50 p-2 text-xs text-rose-700">
                        {err}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {run.dead_letters.length > 0 && (
            <section className="mt-6">
              <h2 className="mb-3 text-sm font-semibold text-gray-700">
                Dead letters ({run.dead_letters.length})
              </h2>
              <div className="space-y-2">
                {run.dead_letters.map((dl, i) => (
                  <div
                    key={`${dl.step_id}-${i}`}
                    className="rounded-lg border border-rose-200 bg-rose-50 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-rose-800">
                        {dl.step_id}
                      </span>
                      <span className="text-xs text-rose-500">
                        {dl.attempts} attempts · {dl.task}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-rose-700">{dl.error}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

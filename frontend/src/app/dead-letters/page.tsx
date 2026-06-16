"use client";

import { useCallback, useEffect, useState } from "react";
import { Inbox, RefreshCw } from "lucide-react";
import type { DeadLetter } from "@/types";
import { apiClient, ApiError } from "@/lib/api";
import { isDemoMode } from "@/lib/demoMode";
import DeadLetterTable from "@/components/DeadLetterTable";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { TableSkeleton } from "@/components/LoadingSkeleton";

export default function DeadLettersPage() {
  const [items, setItems] = useState<DeadLetter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunningRunId, setRerunningRunId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listDeadLetters();
      setItems(data.dead_letters);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dead letters.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRerun = async (runId: string) => {
    setRerunningRunId(runId);
    setToast(null);
    try {
      if (isDemoMode()) {
        setToast("Demo mode: rerun is simulated (no backend to dispatch to).");
        return;
      }
      const res = await apiClient.rerunWorkflow(runId);
      setToast(
        res.dispatched === "async"
          ? `Re-dispatched run ${runId.slice(0, 8)}… asynchronously.`
          : `Reran run ${runId.slice(0, 8)}… → ${res.status}.`
      );
      await load();
    } catch (err) {
      setToast(
        err instanceof ApiError
          ? `Rerun failed: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Rerun failed."
      );
    } finally {
      setRerunningRunId(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <Inbox className="h-6 w-6 text-brand-600" />
            Dead-letter queue
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Steps that exhausted their retries. Rerun the owning workflow to
            retry from scratch.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {toast && (
        <div className="mb-6 rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm text-brand-700">
          {toast}
        </div>
      )}

      {loading ? (
        <TableSkeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No dead letters"
          message="Every step has completed within its retry budget. Nothing to retry."
          icon={Inbox}
        />
      ) : (
        <DeadLetterTable
          deadLetters={items}
          onRerun={handleRerun}
          rerunningRunId={rerunningRunId}
        />
      )}
    </div>
  );
}

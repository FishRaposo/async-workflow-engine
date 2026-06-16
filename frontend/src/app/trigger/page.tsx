"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, PlayCircle, XCircle } from "lucide-react";
import type { DispatchResult, ValidateResult } from "@/types";
import { apiClient, ApiError } from "@/lib/api";
import { isDemoMode } from "@/lib/demoMode";
import { SAMPLE_YAML } from "@/lib/mockData";
import StatusBadge from "@/components/StatusBadge";

type Feedback =
  | { kind: "validated"; data: ValidateResult }
  | { kind: "invalid"; message: string }
  | { kind: "dispatched"; data: DispatchResult }
  | { kind: "error"; message: string }
  | { kind: "demo"; message: string };

export default function TriggerPage() {
  const [yaml, setYaml] = useState(SAMPLE_YAML);
  const [asyncDispatch, setAsyncDispatch] = useState(false);
  const [busy, setBusy] = useState<null | "validate" | "run">(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const handleValidate = async () => {
    setBusy("validate");
    setFeedback(null);
    try {
      if (isDemoMode()) {
        setFeedback({
          kind: "demo",
          message:
            "Demo mode: validation requires the backend. Start the API to validate against the task registry.",
        });
        return;
      }
      const data = await apiClient.validateWorkflow(yaml);
      setFeedback({ kind: "validated", data });
    } catch (err) {
      setFeedback({
        kind: "invalid",
        message:
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Validation failed.",
      });
    } finally {
      setBusy(null);
    }
  };

  const handleRun = async () => {
    setBusy("run");
    setFeedback(null);
    try {
      if (isDemoMode()) {
        setFeedback({
          kind: "demo",
          message:
            "Demo mode: dispatch requires the backend. Start the API to actually run this workflow.",
        });
        return;
      }
      const data = await apiClient.runWorkflow(yaml, asyncDispatch);
      setFeedback({ kind: "dispatched", data });
    } catch (err) {
      setFeedback({
        kind: "error",
        message:
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Dispatch failed.",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <PlayCircle className="h-6 w-6 text-brand-600" />
          Trigger a workflow
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Paste a YAML workflow definition, validate it against the task
          registry, then dispatch it synchronously or onto the async queue.
        </p>
      </div>

      <div className="card">
        <label
          htmlFor="yaml"
          className="mb-2 block text-sm font-semibold text-gray-700"
        >
          Workflow YAML
        </label>
        <textarea
          id="yaml"
          value={yaml}
          onChange={(e) => setYaml(e.target.value)}
          spellCheck={false}
          rows={20}
          className="w-full rounded-lg border border-gray-300 bg-gray-50 p-3 font-mono text-xs text-gray-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={asyncDispatch}
              onChange={(e) => setAsyncDispatch(e.target.checked)}
              className="h-4 w-4 accent-brand-600"
            />
            Async dispatch (enqueue on Celery instead of running inline)
          </label>
          <div className="flex gap-2">
            <button
              onClick={handleValidate}
              disabled={busy !== null}
              className="btn-secondary"
            >
              {busy === "validate" ? "Validating…" : "Validate"}
            </button>
            <button
              onClick={handleRun}
              disabled={busy !== null}
              className="btn-primary"
            >
              {busy === "run" ? "Dispatching…" : "Run workflow"}
            </button>
          </div>
        </div>
      </div>

      {feedback && (
        <div className="mt-6" data-testid="trigger-feedback">
          {feedback.kind === "validated" && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
              <div className="flex items-center gap-2 text-emerald-800">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-semibold">
                  Valid — “{feedback.data.workflow}” has{" "}
                  {feedback.data.steps.length} step
                  {feedback.data.steps.length === 1 ? "" : "s"}.
                </span>
              </div>
              <ul className="mt-3 space-y-1 text-sm text-emerald-700">
                {feedback.data.steps.map((s) => (
                  <li key={s.id} className="font-mono text-xs">
                    {s.id} → {s.task}
                    {s.depends_on.length > 0 &&
                      ` (depends on ${s.depends_on.join(", ")})`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {feedback.kind === "invalid" && (
            <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-4 text-rose-800">
              <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <div>
                <p className="font-semibold">Invalid workflow</p>
                <p className="mt-1 text-sm text-rose-700">{feedback.message}</p>
              </div>
            </div>
          )}

          {feedback.kind === "dispatched" && (
            <div className="rounded-lg border border-brand-200 bg-brand-50 p-4">
              {feedback.data.dispatched === "async" ? (
                <p className="text-sm text-brand-800">
                  Enqueued asynchronously. Task id{" "}
                  <span className="font-mono">{feedback.data.task_id}</span>.
                </p>
              ) : (
                <div>
                  <div className="flex items-center gap-2 text-brand-800">
                    <span className="font-semibold">Run finished</span>
                    <StatusBadge status={feedback.data.status} kind="run" />
                  </div>
                  <Link
                    href={`/runs/${feedback.data.run_id}`}
                    className="mt-2 inline-block text-sm font-medium text-brand-700 underline"
                  >
                    View run {feedback.data.run_id.slice(0, 8)}…
                  </Link>
                </div>
              )}
            </div>
          )}

          {feedback.kind === "error" && (
            <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-4 text-rose-800">
              <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
              <p className="text-sm">{feedback.message}</p>
            </div>
          )}

          {feedback.kind === "demo" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {feedback.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

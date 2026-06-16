"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Plus, RefreshCw } from "lucide-react";
import type { Schedule } from "@/types";
import { apiClient, ApiError } from "@/lib/api";
import { isDemoMode } from "@/lib/demoMode";
import { SAMPLE_YAML } from "@/lib/mockData";
import ScheduleList from "@/components/ScheduleList";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import { TableSkeleton } from "@/components/LoadingSkeleton";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [cron, setCron] = useState("*/15 * * * *");
  const [yaml, setYaml] = useState(SAMPLE_YAML);
  const [submitting, setSubmitting] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.listSchedules();
      setSchedules(data.schedules);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load schedules.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setToast(null);
    try {
      if (isDemoMode()) {
        setToast(
          "Demo mode: creating schedules requires the backend. Start the API to register a cron schedule."
        );
        return;
      }
      const res = await apiClient.createSchedule(name, cron, yaml);
      setToast(`Registered “${res.name}” — next run ${res.next_run ?? "n/a"}.`);
      setName("");
      await load();
    } catch (err) {
      setToast(
        err instanceof ApiError
          ? `Couldn't create schedule: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Couldn't create schedule."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (scheduleName: string) => {
    setDeletingName(scheduleName);
    setToast(null);
    try {
      if (isDemoMode()) {
        setToast("Demo mode: deleting schedules requires the backend.");
        return;
      }
      await apiClient.deleteSchedule(scheduleName);
      setToast(`Deleted “${scheduleName}”.`);
      await load();
    } catch (err) {
      setToast(
        err instanceof Error ? err.message : "Couldn't delete schedule."
      );
    } finally {
      setDeletingName(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <CalendarClock className="h-6 w-6 text-brand-600" />
            Schedules
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Cron-scheduled workflows. The scheduler computes the next fire time
            from each cron expression.
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

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          {loading ? (
            <TableSkeleton rows={3} />
          ) : error ? (
            <ErrorState message={error} onRetry={load} />
          ) : schedules.length === 0 ? (
            <EmptyState
              title="No schedules yet"
              message="Register a cron schedule with the form to fire a workflow on a recurring basis."
              icon={CalendarClock}
            />
          ) : (
            <ScheduleList
              schedules={schedules}
              onDelete={handleDelete}
              deletingName={deletingName}
            />
          )}
        </div>

        <div className="lg:col-span-5">
          <form onSubmit={handleCreate} className="card space-y-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Plus className="h-4 w-4" />
              New schedule
            </h2>
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">
                Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="lead_intake_every_15m"
                className="w-full rounded-lg border border-gray-300 p-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">
                Cron expression
              </label>
              <input
                value={cron}
                onChange={(e) => setCron(e.target.value)}
                required
                placeholder="*/15 * * * *"
                className="w-full rounded-lg border border-gray-300 p-2 font-mono text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">
                Workflow YAML
              </label>
              <textarea
                value={yaml}
                onChange={(e) => setYaml(e.target.value)}
                rows={8}
                spellCheck={false}
                className="w-full rounded-lg border border-gray-300 bg-gray-50 p-2 font-mono text-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full"
            >
              {submitting ? "Registering…" : "Register schedule"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

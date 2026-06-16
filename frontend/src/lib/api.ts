import type {
  DagResponse,
  DeadLetterResponse,
  DispatchResult,
  HealthCheck,
  RunDetail,
  RunListResponse,
  ScheduleCreated,
  ScheduleListResponse,
  TaskListResponse,
  ValidateResult,
} from "@/types";
import { setDemoMode } from "@/lib/demoMode";
import {
  mockDagFor,
  mockDeadLetters,
  mockRunDetails,
  mockRuns,
  mockSchedules,
  mockTasks,
} from "@/lib/mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Thrown when the backend returns a non-2xx response (a real, reportable
 * error — distinct from a network failure, which triggers demo-mode fallback). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const body = await response
        .json()
        .catch(() => ({ detail: response.statusText }));
      throw new ApiError(
        body.detail || `API error: ${response.status}`,
        response.status
      );
    }

    // A successful live call means we are not in demo mode.
    setDemoMode(false);
    return response.json();
  }

  /**
   * Run a live request, falling back to bundled mock data on a *network*
   * failure (backend unreachable). A real HTTP error (4xx/5xx) is re-thrown so
   * callers can surface it. On fallback we flip the global demo-mode flag.
   */
  private async withFallback<T>(
    live: () => Promise<T>,
    fallback: () => T
  ): Promise<T> {
    try {
      return await live();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      setDemoMode(true);
      return fallback();
    }
  }

  // ---- Runs ---------------------------------------------------------------- //
  listRuns(): Promise<RunListResponse> {
    return this.withFallback(
      () => this.request<RunListResponse>("/workflows"),
      () => ({ runs: mockRuns })
    );
  }

  getRun(runId: string): Promise<RunDetail> {
    return this.withFallback(
      () => this.request<RunDetail>(`/workflows/${runId}`),
      () => {
        const detail = mockRunDetails[runId];
        if (!detail) throw new ApiError(`Run '${runId}' not found`, 404);
        return detail;
      }
    );
  }

  getDag(runId: string): Promise<DagResponse> {
    return this.withFallback(
      () => this.request<DagResponse>(`/workflows/${runId}/dag`),
      () => mockDagFor(runId)
    );
  }

  // ---- Trigger / validate / rerun ----------------------------------------- //
  validateWorkflow(yamlDefinition: string): Promise<ValidateResult> {
    return this.request<ValidateResult>("/workflows/validate", {
      method: "POST",
      body: JSON.stringify({ yaml_definition: yamlDefinition }),
    });
  }

  runWorkflow(
    yamlDefinition: string,
    asyncDispatch = false
  ): Promise<DispatchResult> {
    return this.request<DispatchResult>("/workflows/run", {
      method: "POST",
      body: JSON.stringify({
        yaml_definition: yamlDefinition,
        async_dispatch: asyncDispatch,
      }),
    });
  }

  rerunWorkflow(runId: string, asyncDispatch = false): Promise<DispatchResult> {
    return this.request<DispatchResult>(`/workflows/${runId}/rerun`, {
      method: "POST",
      body: JSON.stringify({ async_dispatch: asyncDispatch }),
    });
  }

  // ---- Dead-letter queue --------------------------------------------------- //
  listDeadLetters(runId?: string): Promise<DeadLetterResponse> {
    const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return this.withFallback(
      () => this.request<DeadLetterResponse>(`/workflows/dead-letters${qs}`),
      () => ({
        dead_letters: runId
          ? mockDeadLetters.filter((dl) => dl.run_id === runId)
          : mockDeadLetters,
      })
    );
  }

  // ---- Schedules ----------------------------------------------------------- //
  listSchedules(): Promise<ScheduleListResponse> {
    return this.withFallback(
      () => this.request<ScheduleListResponse>("/schedules"),
      () => ({ schedules: mockSchedules })
    );
  }

  createSchedule(
    name: string,
    cron: string,
    yamlDefinition: string
  ): Promise<ScheduleCreated> {
    return this.request<ScheduleCreated>("/schedules", {
      method: "POST",
      body: JSON.stringify({
        name,
        cron,
        yaml_definition: yamlDefinition,
      }),
    });
  }

  deleteSchedule(name: string): Promise<{ deleted: string }> {
    return this.request<{ deleted: string }>(
      `/schedules/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
  }

  // ---- Introspection ------------------------------------------------------- //
  listTasks(): Promise<TaskListResponse> {
    return this.withFallback(
      () => this.request<TaskListResponse>("/tasks"),
      () => ({ tasks: mockTasks })
    );
  }

  healthCheck(): Promise<HealthCheck> {
    return this.request<HealthCheck>("/health");
  }
}

export const apiClient = new ApiClient(API_BASE);
